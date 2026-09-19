import os
import json
import math
import httpx
import re

from typing import TypedDict
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, END

# ── LLM ───────────────────────────────────────────────────
load_dotenv()

llm = ChatGoogleGenerativeAI(
    model="gemini-3.8-flash",
    google_api_key=os.getenv("GEMINI_API_KEY"),
    temperature=0.1,
    max_tokens=1024,
)

# ── State ─────────────────────────────────────────────────
class AgentState(TypedDict, total=False):
    session_id: str
    events: list
    lat: float
    lon: float
    crash_speed: float
    max_speed: float
    peak_accel: float
    peak_ax: float
    peak_ay: float
    peak_az: float
    delta_vx: float
    delta_vy: float
    delta_vz: float
    delta_v_total: float
    collision_type: str
    impact_angle: float
    crash_idx: int
    location_name: str
    weather: str
    speed_limit: str
    severity: str
    severity_score: int
    report: dict

# ── Node 1 ────────────────────────────────────────────────
def analyze_telemetry(state: AgentState) -> AgentState:
    events = state.get("events", [])
    if not events:
        return {**state, "lat": 0.0, "lon": 0.0, "crash_speed": 0.0,
                "max_speed": 0.0, "peak_accel": 0.0, "crash_idx": 0}

    speeds = [e["speed"] for e in events]
    accel_mags = [math.sqrt(e["ax"]**2 + e["ay"]**2 + e["az"]**2) for e in events]

    crash_idx, max_drop = 0, 0
    for i in range(1, len(speeds)):
        drop = speeds[i - 1] - speeds[i]
        if drop > max_drop:
            max_drop = drop
            crash_idx = i

    crash_speed = speeds[crash_idx - 1] if crash_idx > 0 else speeds[0]

    return {
        **state,
        "lat":        events[crash_idx]["lat"],
        "lon":        events[crash_idx]["lon"],
        "crash_speed": crash_speed,
        "max_speed":  max(speeds),
        "peak_accel": round(max(accel_mags), 2),
        "crash_idx":  crash_idx,
    }

# ── Node 2 ────────────────────────────────────────────────
def calculate_delta_v(state: AgentState) -> AgentState:
    events = state.get("events", [])
    if len(events) < 2:
        return {**state, "delta_vx": 0.0, "delta_vy": 0.0, "delta_vz": 0.0,
                "delta_v_total": 0.0, "peak_ax": 0.0, "peak_ay": 0.0, "peak_az": 0.0}

    crash_idx = state.get("crash_idx", 0)
    window = 10
    crash_events = events[max(0, crash_idx - window):min(len(events), crash_idx + window + 1)]
    dt = 0.1

    dvx = dvy = dvz = 0.0
    peak_ax = peak_ay = peak_az = 0.0

    for e in crash_events:
        dvx += e["ax"] * dt
        dvy += e["ay"] * dt
        dvz += e["az"] * dt
        peak_ax = max(peak_ax, abs(e["ax"]))
        peak_ay = max(peak_ay, abs(e["ay"]))
        peak_az = max(peak_az, abs(e["az"]))

    return {
        **state,
        "delta_vx": round(dvx, 2), "delta_vy": round(dvy, 2), "delta_vz": round(dvz, 2),
        "delta_v_total": round(math.sqrt(dvx**2 + dvy**2 + dvz**2), 2),
        "peak_ax": round(peak_ax, 2), "peak_ay": round(peak_ay, 2), "peak_az": round(peak_az, 2),
    }

# ── Node 3 ────────────────────────────────────────────────
def detect_collision_direction(state: AgentState) -> AgentState:
    dvx = state.get("delta_vx", 0.0)
    dvz = state.get("delta_vz", 0.0)
    peak_ay = state.get("peak_ay", 0.0)
    abs_x, abs_y, abs_z = abs(dvx), abs(state.get("delta_vy", 0.0)), abs(dvz)

    if peak_ay > 8:
        collision_type = "ROLLOVER"
    elif abs_x > 5 and abs_z > 5:
        collision_type = "DIAGONAL_COLLISION"
    elif abs_z >= abs_x and abs_z >= abs_y:
        collision_type = "FRONT_COLLISION" if dvz < 0 else "REAR_COLLISION"
    elif abs_x >= abs_z and abs_x >= abs_y:
        collision_type = "LEFT_SIDE_IMPACT" if dvx > 0 else "RIGHT_SIDE_IMPACT"
    else:
        collision_type = "UNKNOWN"

    return {**state, "collision_type": collision_type,
            "impact_angle": round(math.degrees(math.atan2(dvx, dvz)), 2)}

# ── Node 4 ────────────────────────────────────────────────
async def get_landmark(state: AgentState) -> AgentState:
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get("https://nominatim.openstreetmap.org/reverse",
                params={"lat": state["lat"], "lon": state["lon"], "format": "json"},
                headers={"User-Agent": "BlackboxApp/1.0"})
        display = r.json().get("display_name", f"{state['lat']:.4f}, {state['lon']:.4f}")
    except Exception:
        display = f"{state.get('lat', 0):.4f}, {state.get('lon', 0):.4f}"
    return {**state, "location_name": display}

# ── Node 5 ────────────────────────────────────────────────
async def get_weather(state: AgentState) -> AgentState:
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get("https://api.open-meteo.com/v1/forecast",
                params={"latitude": state["lat"], "longitude": state["lon"],
                        "current": "temperature_2m,weathercode,windspeed_10m",
                        "timezone": "auto"})
        d = r.json().get("current", {})
        weather_str = f"{d.get('temperature_2m','?')}°C, wind {d.get('windspeed_10m','?')} km/h, code {d.get('weathercode','?')}"
    except Exception:
        weather_str = "Unavailable"
    return {**state, "weather": weather_str}

# ── Node 6 ────────────────────────────────────────────────
async def get_speed_limit(state: AgentState) -> AgentState:
    try:
        query = f"[out:json];way(around:30,{state['lat']},{state['lon']})[highway][maxspeed];out 1;"
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post("https://overpass-api.de/api/interpreter", data={"data": query})
        elements = r.json().get("elements", [])
        limit = elements[0].get("tags", {}).get("maxspeed", "Unknown") if elements else "Unknown"
    except Exception:
        limit = "Unknown"
    return {**state, "speed_limit": limit}

# ── Node 7 ────────────────────────────────────────────────
def determine_severity(state: AgentState) -> AgentState:
    dv = abs(state.get("delta_v_total", 0.0))
    peak_accel = math.sqrt(state.get("peak_ax",0)**2 + state.get("peak_ay",0)**2 + state.get("peak_az",0)**2)
    impact_angle = abs(state.get("impact_angle", 0.0))
    collision_type = state.get("collision_type", "UNKNOWN")

    score = 0
    if dv >= 40: score += 5
    elif dv >= 25: score += 4
    elif dv >= 15: score += 3
    elif dv >= 8: score += 2

    if peak_accel >= 20: score += 5
    elif peak_accel >= 15: score += 4
    elif peak_accel >= 10: score += 3
    elif peak_accel >= 6: score += 2

    if 60 <= impact_angle <= 120: score += 2
    if collision_type == "ROLLOVER": score += 5
    if collision_type == "DIAGONAL_COLLISION": score += 2
    if state.get("max_speed", 0) >= 100: score += 2

    if score >= 10: severity = "CRITICAL"
    elif score >= 7: severity = "SEVERE"
    elif score >= 4: severity = "MODERATE"
    else: severity = "MINOR"

    return {**state, "severity": severity, "severity_score": score}

# ── Node 8 ────────────────────────────────────────────────
async def generate_report(state: AgentState) -> AgentState:
    prompt = f"""You are a forensic vehicle accident AI.
Generate a structured JSON accident report. Return ONLY valid JSON — no markdown, no backticks, no explanation.

DATA:
- Location: {state.get('location_name', 'Unknown')}
- Weather: {state.get('weather', 'Unknown')}
- Speed limit: {state.get('speed_limit', 'Unknown')}
- Max speed before crash: {state.get('max_speed', 0)} km/h
- Speed at impact: {state.get('crash_speed', 0)} km/h
- Delta Vx / Vy / Vz: {state.get('delta_vx',0)} / {state.get('delta_vy',0)} / {state.get('delta_vz',0)} m/s
- Total Delta-V: {state.get('delta_v_total', 0)} m/s
- Peak accel X/Y/Z: {state.get('peak_ax',0)} / {state.get('peak_ay',0)} / {state.get('peak_az',0)}
- Collision type: {state.get('collision_type', 'UNKNOWN')}
- Impact angle: {state.get('impact_angle', 0)}°
- Severity: {state.get('severity', 'UNKNOWN')} (score: {state.get('severity_score', 0)})

OUTPUT FORMAT (JSON only, absolutely no other text before or after):
{{
  "summary": "",
  "collision_type": "",
  "impact_angle": 0,
  "location": "",
  "weather": "",
  "speed_limit": "",
  "max_speed": 0,
  "impact_speed": 0,
  "delta_v_total": 0,
  "severity": "",
  "severity_score": 0,
  "emergency_action": ""
}}"""

    try:
        print("[REPORT] Invoking Gemini 3.8 Flash...")
        response = await llm.ainvoke(prompt)
        print(f"[REPORT] Raw: {response.content[:300]}")

        text = response.content.strip()
        text = re.sub(r'^```(?:json)?\s*', '', text, flags=re.MULTILINE)
        text = re.sub(r'\s*```$', '', text, flags=re.MULTILINE)
        text = text.strip()

        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            text = match.group(0)

        report_json = json.loads(text)
        print("[REPORT] Parsed successfully")

    except json.JSONDecodeError as e:
        print(f"[REPORT] JSON error: {e}")
        report_json = _fallback_report(state)
    except Exception as e:
        print(f"[REPORT] LLM error: {type(e).__name__}: {e}")
        import traceback; traceback.print_exc()
        report_json = _fallback_report(state)

    return {**state, "report": report_json}


def _fallback_report(state: dict) -> dict:
    return {
        "summary": (
            f"Vehicle crash detected. {state.get('collision_type','Unknown')} impact "
            f"at {state.get('crash_speed', 0):.1f} km/h. "
            f"Total delta-V: {state.get('delta_v_total', 0):.1f} m/s."
        ),
        "collision_type": state.get("collision_type", "UNKNOWN"),
        "impact_angle":   state.get("impact_angle", 0),
        "location":       state.get("location_name", "Unknown"),
        "weather":        state.get("weather", "Unknown"),
        "speed_limit":    state.get("speed_limit", "Unknown"),
        "max_speed":      state.get("max_speed", 0),
        "impact_speed":   state.get("crash_speed", 0),
        "delta_v_total":  state.get("delta_v_total", 0),
        "severity":       state.get("severity", "UNKNOWN"),
        "severity_score": state.get("severity_score", 0),
        "emergency_action": "Contact emergency services immediately.",
    }

# ── Graph ─────────────────────────────────────────────────
def build_graph():
    g = StateGraph(AgentState)
    g.add_node("analyze",                   analyze_telemetry)
    g.add_node("calculate_delta_v",         calculate_delta_v)
    g.add_node("detect_collision_direction", detect_collision_direction)
    g.add_node("get_landmark",              get_landmark)
    g.add_node("get_weather",               get_weather)
    g.add_node("get_speed_limit",           get_speed_limit)
    g.add_node("determine_severity",        determine_severity)
    g.add_node("generate_report",           generate_report)

    g.set_entry_point("analyze")
    g.add_edge("analyze",                    "calculate_delta_v")
    g.add_edge("calculate_delta_v",          "detect_collision_direction")
    g.add_edge("detect_collision_direction", "get_landmark")
    g.add_edge("get_landmark",               "get_weather")
    g.add_edge("get_weather",                "get_speed_limit")
    g.add_edge("get_speed_limit",            "determine_severity")
    g.add_edge("determine_severity",         "generate_report")
    g.add_edge("generate_report",            END)
    return g.compile()

blackbox_graph = build_graph()