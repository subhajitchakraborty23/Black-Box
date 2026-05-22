from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc
from pydantic import BaseModel
from datetime import datetime
from uuid import UUID
import uuid, json

from db import get_db, session_local
from auth import get_current_user
from models import User, TelemetrySession, TelemetryEvent, CrashReport
from agent.graph import blackbox_graph

router = APIRouter(prefix="/telemetry", tags=["telemetry"])

SPEED_DROP_THRESHOLD = 30.0  
ACCEL_SPIKE_THRESHOLD = 8.0   
DELTA_V_THRESHOLD = 4.0       
JERK_THRESHOLD = 30.0         

class SessionOut(BaseModel):
    session_id: UUID

class EventIn(BaseModel):
    session_id: UUID
    lat: float
    lon: float
    speed: float     
    accel: float    
    ax: float = 0.0
    ay: float = 0.0
    az: float = 0.0  
    timestamp: datetime

class EventOut(BaseModel):
    event_id: UUID
    crash_detected: bool

def _detect_crash(prev: TelemetryEvent | None, current: EventIn) -> bool:
    if prev is None:
        return False

    dt = max((current.timestamp - prev.timestamp).total_seconds(), 0.1)
    speed_drop = prev.speed - current.speed                    # km/h
    delta_v    = speed_drop / 3.6                              # m/s
    jerk       = abs(current.accel - prev.accel) / dt / 9.81  # g/s

    return (
        speed_drop >= SPEED_DROP_THRESHOLD or
        current.accel >= ACCEL_SPIKE_THRESHOLD or
        delta_v >= DELTA_V_THRESHOLD or
        jerk >= JERK_THRESHOLD
    )


@router.post("/session/start", response_model=SessionOut)
async def start_session(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    try:
        session = TelemetrySession(user_id=user.id)
        db.add(session)
        await db.commit()
        await db.refresh(session)
        return {"session_id": session.id}
    except Exception as e:
        print(f"Error starting session: {e}")
        raise HTTPException(500, "Failed to start telemetry session")


@router.post("/session/end/{session_id}")
async def end_session(
    session_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    try:
        result = await db.execute(
            select(TelemetrySession).where(TelemetrySession.id == session_id)
        )
        s = result.scalar_one_or_none()
        if s:
            s.is_active = False
            s.ended_at = datetime.utcnow()
            await db.commit()
        return {"status": "ended"}
    except Exception as e:
        print(f"Error ending session: {e}")
        raise HTTPException(500, "Failed to end telemetry session")


@router.post("/event", response_model=EventOut)
async def post_event(
    payload: EventIn,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    try:
        # Strip timezone info from incoming timestamp to match database naive datetimes
        payload.timestamp = payload.timestamp.replace(tzinfo=None) if payload.timestamp.tzinfo else payload.timestamp
        
        result = await db.execute(
            select(TelemetryEvent)
            .where(TelemetryEvent.session_id == payload.session_id)
            .order_by(TelemetryEvent.timestamp.desc())
            .limit(1)
        )
        prev = result.scalar_one_or_none()
        crash_detected = _detect_crash(prev, payload)

        event = TelemetryEvent(
            session_id=payload.session_id,
            lat=payload.lat,
            lon=payload.lon,
            speed=payload.speed,
            accel=payload.accel,
            ax=payload.ax,
            ay=payload.ay,
            az=payload.az,
            timestamp=payload.timestamp,
            crash_flagged=crash_detected
        )
        db.add(event)
        await db.commit()
        await db.refresh(event)

        return {"event_id": event.id, "crash_detected": crash_detected}
    except Exception as e:
        print(f"Error posting event: {e}")
        raise HTTPException(500, "Failed to record telemetry event")


@router.post("/false-alarm/{session_id}")
async def false_alarm(
    session_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """User said 'I'm fine' — unmark the crash flag."""
    try:
        result = await db.execute(
            select(TelemetryEvent)
            .where(
                and_(
                    TelemetryEvent.session_id == session_id,
                    TelemetryEvent.crash_flagged == True
                )
            )
            .order_by(TelemetryEvent.timestamp.desc())
            .limit(1)
        )
        event = result.scalar_one_or_none()
        if event:
            event.crash_flagged = False
            await db.commit()
        return {"status": "false_alarm_logged"}
    except Exception as e:
        print(f"Error in false_alarm: {e}")
        raise HTTPException(500, "Failed to log false alarm")


@router.post("/reconstruct/{session_id}")
async def reconstruct(
    session_id: UUID,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """User confirmed crash (or 20s elapsed) — run AI agent."""
    background_tasks.add_task(_run_agent, str(session_id))
    return {"status": "reconstruction_started", "session_id": str(session_id)}


@router.get("/report/{session_id}")
async def get_report(
    session_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(CrashReport)
        .where(CrashReport.session_id == session_id)
        .order_by(desc(CrashReport.created_at))
        .limit(1)
    )
    report = result.scalar_one_or_none()
    if not report:
        return {"status": "pending"}
    return {
        "status": "ready",
        "session_id": str(session_id),
        "severity": report.severity,
        "report": report.report, 
        "created_at": report.created_at,
    }


@router.get("/sessions")
async def list_sessions(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(TelemetrySession)
        .where(TelemetrySession.user_id == user.id)
        .order_by(TelemetrySession.started_at.desc())
    )
    sessions = result.scalars().all()
    return [
        {
            "session_id": str(s.id),
            "started_at": s.started_at,
            "ended_at": s.ended_at,
            "is_active": s.is_active,
        }
        for s in sessions
    ]


@router.delete("/session/{session_id}")
async def delete_session(
    session_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(TelemetrySession).where(TelemetrySession.id == session_id)
    )
    s = result.scalar_one_or_none()
    if s:
        await db.delete(s)
        await db.commit()
    return {"status": "deleted"}


async def _run_agent(session_id: str):
    print(f"[AGENT] Starting reconstruction for session {session_id}")
    async with session_local() as db:
        try:
            print(f"[AGENT] Converting session_id to UUID: {session_id}")
            session_uuid = UUID(session_id)
            print(f"[AGENT] UUID conversion successful: {session_uuid}")
            
            print(f"[AGENT] Querying telemetry events for session {session_uuid}")
            result = await db.execute(
                select(TelemetryEvent)
                .where(TelemetryEvent.session_id == session_uuid)
                .order_by(TelemetryEvent.timestamp.asc())
            )
            events = result.scalars().all()
            print(f"[AGENT] Found {len(events)} events for session")

            if not events:
                print(f"[AGENT] No events found for session {session_id}")
                return

            print(f"[AGENT] Building events_data from {len(events)} events")
            events_data = [
                {
                    "lat":   e.lat,
                    "lon":   e.lon,
                    "speed": e.speed,
                    "accel": e.accel,
                    "ax":    e.ax,
                    "ay":    e.ay,
                    "az":    e.az,
                    "timestamp": e.timestamp.isoformat(),
                }
                for e in events
            ]
            print(f"[AGENT] Successfully built events_data")

            print(f"[AGENT] Invoking blackbox_graph agent")
            final_state = await blackbox_graph.ainvoke({
                "session_id": session_id,
                "events":     events_data,
                "lat": 0.0, "lon": 0.0,
                "crash_speed": 0.0, "max_speed": 0.0, "peak_accel": 0.0,
                "peak_ax": 0.0, "peak_ay": 0.0, "peak_az": 0.0,
                "delta_vx": 0.0, "delta_vy": 0.0, "delta_vz": 0.0, "delta_v_total": 0.0,
                "collision_type": "UNKNOWN", "impact_angle": 0.0,
                "crash_idx": 0,
                "location_name": "", "weather": "", "speed_limit": "",
                "severity": "MINOR", "severity_score": 0, "report": {}
            })
            print(f"[AGENT] Agent invocation complete. Severity: {final_state.get('severity', 'UNKNOWN')}")
            print(f"[AGENT] Final state keys: {list(final_state.keys())}")

            # Save to crash_reports table
            import json as _json
            print(f"[AGENT] Creating CrashReport object with session_uuid={session_uuid}")
            report = CrashReport(
                session_id=session_uuid,
                severity=final_state.get("severity", "UNKNOWN"),
                report=_json.dumps(final_state.get("report", {}))
            )
            print(f"[AGENT] CrashReport created. Saving to database...")
            db.add(report)
            await db.commit()
            print(f"[AGENT] CrashReport saved successfully")
            print(f"[AGENT] Done — severity: {final_state.get('severity', 'UNKNOWN')}")

            if final_state.get("severity") in ("SEVERE", "CRITICAL"):
                await _trigger_emergency(final_state)

        except Exception as e:
            print(f"[AGENT] Error: {type(e).__name__}: {e}")
            import traceback; traceback.print_exc()


async def _trigger_emergency(state: dict):
    # Step 6 — Twilio call goes here
    print(f"[EMERGENCY] Would call ambulance for severity {state['severity']} at {state.get('location_name')}")

