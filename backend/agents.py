from google import genai
import os
from dotenv import load_dotenv
from tools import (
    get_nearest_landmark,
    get_weather_at_crash,
    get_speed_limit,
    analyze_gps_data,
    determine_severity,
    validate_data_for_prompt,   # ✅ NEW — hallucination prevention
)

load_dotenv()

client = genai.Client()



def format_gps_data(readings: list) -> str:
    formatted = ""
    for i, entry in enumerate(readings):
        formatted += f"""
Reading {i+1}:
  Timestamp  : {entry['timestamp']}
  Latitude   : {entry['latitude']}
  Longitude  : {entry['longitude']}
  Altitude   : {entry['altitude_m']} m
  Speed      : {entry['speed_kmph']} km/h
  Satellites : {entry['satellites']}
"""
    return formatted



def build_prompt(
    gps_data_str    : str,
    analysis        : dict,
    landmark        : dict,     # ✅ now dict not string
    weather         : dict,     # ✅ now dict not string
    speed_limit     : dict,     # ✅ now dict not string
    severity_info   : dict,
    validated       : dict,     # ✅ NEW — validation results
) -> str:

    #  Safely extract values from dicts
    # If API failed → shows "CANNOT BE DETERMINED"
    landmark_text   = landmark.get("landmark",   "CANNOT BE DETERMINED FROM AVAILABLE DATA")
    landmark_conf   = landmark.get("confidence", "NONE")
    maps_link       = landmark.get("google_maps","N/A")

    weather_text    = weather.get("condition",   "CANNOT BE DETERMINED FROM AVAILABLE DATA")
    weather_temp    = weather.get("temperature", "N/A")
    weather_wind    = weather.get("wind_speed",  "N/A")
    weather_risk    = weather.get("weather_risk","UNKNOWN")
    weather_conf    = weather.get("confidence",  "NONE")
    weather_contrib = weather.get("contributed_to_accident", False)

    speed_lim_text  = speed_limit.get("speed_limit", "CANNOT BE DETERMINED FROM AVAILABLE DATA")
    road_type       = speed_limit.get("road_type",   "CANNOT BE DETERMINED FROM AVAILABLE DATA")
    speed_lim_conf  = speed_limit.get("confidence",  "NONE")

    severity        = severity_info.get("severity",       "CANNOT BE DETERMINED")
    injuries        = severity_info.get("injuries",       "CANNOT BE DETERMINED")
    emergency       = severity_info.get("emergency",      "CANNOT BE DETERMINED")
    sev_conf        = severity_info.get("confidence",     "NONE")
    sev_conf_pct    = severity_info.get("confidence_pct", 0)
    limitations     = severity_info.get("limitations",    [])

    return f"""
You are a certified Accident Reconstruction Analyst and Forensic Engineer.
You have been given raw blackbox GPS data and pre-analyzed context from multiple tools.

{validated['prompt_instructions']}

════════════════════════════════════════════
        TOOL RESULTS (PRE-ANALYZED)
════════════════════════════════════════════

📍 NEAREST LANDMARK
   Location   : {landmark_text}
   Maps Link  : {maps_link}
   Confidence : {landmark_conf}

🌤️  WEATHER AT CRASH SITE
   Condition  : {weather_text}
   Temperature: {weather_temp}
   Wind Speed : {weather_wind}
   Risk Level : {weather_risk}
   Contributed: {"YES ⚠️" if weather_contrib else "NO"}
   Confidence : {weather_conf}

🚦 ROAD INFORMATION
   Road Type  : {road_type}
   Speed Limit: {speed_lim_text}
   Confidence : {speed_lim_conf}

💥 CRASH ANALYSIS (FROM GPS DATA)
   Max Speed        : {analysis.get('max_speed_kmph', 'N/A')} km/h
   Pre-Crash Speed  : {analysis.get('pre_crash_speed', 'N/A')} km/h
   Speed Drop       : {analysis.get('speed_drop_kmph', 'N/A')} km/h
   Deceleration     : {analysis.get('deceleration_g', 'N/A')} g
   Speed Trend      : {analysis.get('speed_trend', 'N/A')}
   Crash Timestamp  : {analysis.get('crash_timestamp', 'N/A')}
   Crash Altitude   : {analysis.get('crash_altitude', 'N/A')}
   Satellites Lost  : {analysis.get('satellites_lost', 'N/A')}
   Initial Sats     : {analysis.get('initial_satellites', 'N/A')}
   Final Sats       : {analysis.get('final_satellites', 'N/A')}
   Impact Direction : {analysis.get('impact_direction', 'CANNOT BE DETERMINED — IMU required')}
   Data Confidence  : {analysis.get('confidence', 'N/A')}

⚠️  SEVERITY ASSESSMENT
   Severity     : {severity}
   Confidence   : {sev_conf} ({sev_conf_pct}%)
   Injury Risk  : {injuries}
   Emergency    : {emergency}
   Limitations  : {', '.join(limitations) if limitations else 'None'}

════════════════════════════════════════════
     GPS BLACKBOX DATA (ALL READINGS)
════════════════════════════════════════════
{gps_data_str}

════════════════════════════════════════════
     ACCIDENT RECONSTRUCTION REPORT
════════════════════════════════════════════

Generate a complete forensic accident reconstruction report:

SECTION 1: PRE-ACCIDENT ANALYSIS
- Speed trend, driver behavior, motion pattern
- Was vehicle speeding based on speed limit?
- Weather contribution assessment

SECTION 2: CRASH MOMENT IDENTIFICATION
- Exact timestamp, speed at impact, GPS coordinates
- Satellite status before and after crash
- Deceleration profile

SECTION 3: PROBABLE CAUSE OF ACCIDENT
- Primary cause (based on DATA only)
- Impact direction (state UNDETERMINED if IMU missing)
- Overspeeding assessment vs speed limit
- Road and weather conditions

SECTION 4: POST-ACCIDENT ANALYSIS
- Post-impact movement
- Final resting state
- Satellite loss explanation

SECTION 5: ACCIDENT SEVERITY ASSESSMENT
- Severity rating with confidence percentage
- Injury risk assessment
- Emergency response recommendation

SECTION 6: RECONSTRUCTION SUMMARY
- Full narrative paragraph
- Event timeline:
  [T-Xs] → Vehicle state before crash
  [T-0 ] → Crash moment
  [T+Xs] → Post-crash state
  [Final] → Resting state

SECTION 7: DATA QUALITY NOTE
- List what was CONFIRMED from data
- List what CANNOT BE DETERMINED
- Overall confidence in this report
- Recommended additional data for better accuracy

════════════════════════════════════════════
IMPORTANT: Mark report as:
"AI ASSISTED FORENSIC REPORT — REQUIRES EXPERT REVIEW"
"NOT FOR LEGAL USE WITHOUT PROFESSIONAL VERIFICATION"
════════════════════════════════════════════
"""


# ─────────────────────────────────────────
# Main Agent Runner — fully upgraded
# ─────────────────────────────────────────
async def run_accident_agent(readings: list, session_id: str) -> dict:
    print(f"\n🤖 BlackBox Agent starting for session: {session_id}")
    print("─" * 50)

    # ── Step 1: Analyze GPS data
    print("📊 Tool 1: Analyzing GPS data...")
    analysis = analyze_gps_data(readings)
    print(f"   Status    : {analysis.get('status')}")
    print(f"   Max Speed : {analysis.get('max_speed_kmph')} km/h")
    print(f"   Crash at  : {analysis.get('crash_timestamp')}")
    print(f"   Confidence: {analysis.get('confidence')}")

    crash_lat = analysis.get("crash_lat")
    crash_lon = analysis.get("crash_lon")

    # ── Step 2: Get nearest landmark
    print("\n📍 Tool 2: Fetching nearest landmark...")
    if crash_lat and crash_lon:
        landmark = await get_nearest_landmark(crash_lat, crash_lon)
    else:
        landmark = {
            "status"     : "FAILED",
            "landmark"   : "CANNOT BE DETERMINED FROM AVAILABLE DATA",
            "confidence" : "NONE",
            "note"       : "Crash location not detected from GPS"
        }
    print(f"   Status    : {landmark.get('status')}")
    print(f"   Location  : {landmark.get('landmark')}")
    print(f"   Confidence: {landmark.get('confidence')}")

    # ── Step 3: Get weather
    print("\n🌤️  Tool 3: Fetching weather at crash site...")
    if crash_lat and crash_lon:
        weather = await get_weather_at_crash(crash_lat, crash_lon)
    else:
        weather = {
            "status"                  : "FAILED",
            "condition"               : "CANNOT BE DETERMINED FROM AVAILABLE DATA",
            "temperature"             : "N/A",
            "wind_speed"              : "N/A",
            "weather_risk"            : "UNKNOWN",
            "confidence"              : "NONE",
            "contributed_to_accident" : False,
            "note"                    : "Crash location not detected"
        }
    print(f"   Status    : {weather.get('status')}")
    print(f"   Condition : {weather.get('condition')}")
    print(f"   Risk      : {weather.get('weather_risk')}")
    print(f"   Confidence: {weather.get('confidence')}")

    # ── Step 4: Get speed limit
    print("\n🚦 Tool 4: Fetching road speed limit...")
    if crash_lat and crash_lon:
        speed_limit = await get_speed_limit(crash_lat, crash_lon)
    else:
        speed_limit = {
            "status"      : "FAILED",
            "road_type"   : "CANNOT BE DETERMINED FROM AVAILABLE DATA",
            "speed_limit" : "CANNOT BE DETERMINED FROM AVAILABLE DATA",
            "confidence"  : "NONE",
            "note"        : "Crash location not detected"
        }
    print(f"   Status    : {speed_limit.get('status')}")
    print(f"   Road Type : {speed_limit.get('road_type')}")
    print(f"   Limit     : {speed_limit.get('speed_limit')}")
    print(f"   Confidence: {speed_limit.get('confidence')}")

    # ── Step 5: Determine severity
    print("\n⚠️  Tool 5: Determining accident severity...")
    severity_info = determine_severity(
        speed_drop = analysis.get("speed_drop_kmph", 0),
        max_speed  = analysis.get("max_speed_kmph",  0),
    )
    print(f"   Severity    : {severity_info.get('severity')}")
    print(f"   Confidence  : {severity_info.get('confidence')} ({severity_info.get('confidence_pct')}%)")

    # ── Step 6: Validate all data before Gemini ✅ NEW
    print("\n🔍 Tool 6: Validating data before AI generation...")
    validated = validate_data_for_prompt(
        analysis    = analysis,
        landmark    = landmark,
        weather     = weather,
        speed_limit = speed_limit,
        severity    = severity_info
    )
    print(f"   Confirmed facts   : {validated['confirmed_facts']}")
    print(f"   Unavailable data  : {validated['unavailable_data']}")
    print(f"   Low confidence    : {validated['low_confidence_data']}")

    # ── Step 7: Build prompt + call Gemini
    print("\n🤖 Tool 7: Sending to Gemini AI for reconstruction...")
    gps_data_str = format_gps_data(readings)
    prompt = build_prompt(
        gps_data_str  = gps_data_str,
        analysis      = analysis,
        landmark      = landmark,
        weather       = weather,
        speed_limit   = speed_limit,
        severity_info = severity_info,
        validated     = validated,      # ✅ pass validation to prompt
    )

    response    = client.models.generate_content(
        model    = "gemini-2.5-flash",
        contents = [{"role": "user", "text": prompt}],
    )
    report_text = response.text

    print("\n✅ Agent completed reconstruction!")
    print("─" * 50)

    # ── Return full structured result ✅ upgraded
    return {
        "session_id"         : session_id,

        # Location
        "crash_gps"          : f"Lat: {crash_lat}, Lon: {crash_lon}" if crash_lat else "Not detected",
        "google_maps_link"   : landmark.get("google_maps", "N/A"),
        "nearest_landmark"   : landmark.get("landmark",    "CANNOT BE DETERMINED"),

        # Environmental
        "weather_at_crash"   : weather.get("condition",    "CANNOT BE DETERMINED"),
        "weather_risk"       : weather.get("weather_risk", "UNKNOWN"),
        "speed_limit"        : speed_limit.get("speed_limit", "CANNOT BE DETERMINED"),
        "road_type"          : speed_limit.get("road_type",   "CANNOT BE DETERMINED"),

        # Crash data
        "severity"           : severity_info.get("severity",     "CANNOT BE DETERMINED"),
        "confidence"         : severity_info.get("confidence",    "NONE"),
        "confidence_pct"     : severity_info.get("confidence_pct", 0),
        "injury_risk"        : severity_info.get("injuries",     "CANNOT BE DETERMINED"),
        "emergency"          : severity_info.get("emergency",    "CANNOT BE DETERMINED"),
        "max_speed_kmph"     : analysis.get("max_speed_kmph",   0),
        "pre_crash_speed"    : analysis.get("pre_crash_speed",  0),
        "speed_drop_kmph"    : analysis.get("speed_drop_kmph",  0),
        "deceleration_g"     : analysis.get("deceleration_g",   "N/A"),
        "speed_trend"        : analysis.get("speed_trend",      "N/A"),
        "crash_timestamp"    : analysis.get("crash_timestamp",  "N/A"),
        "satellites_lost"    : analysis.get("satellites_lost",  False),

        # Confidence & validation ✅ NEW
        "confirmed_facts"    : validated.get("confirmed_facts",    []),
        "unavailable_data"   : validated.get("unavailable_data",   []),
        "low_confidence_data": validated.get("low_confidence_data",[]),

        # Legal ✅ NEW
        "legal_note"         : severity_info.get("legal_note",   "AI ASSISTED — REQUIRES EXPERT REVIEW"),
        "limitations"        : severity_info.get("limitations",  []),
        "data_sources"       : [
            landmark.get("data_source",   "N/A"),
            weather.get("data_source",    "N/A"),
            speed_limit.get("data_source","N/A"),
            "GPS BlackBox Readings"
        ],

        # Report
        "report_text"        : report_text,
        "analysis"           : analysis,
    }