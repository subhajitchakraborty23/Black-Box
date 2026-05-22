from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from datetime import datetime
from uuid import UUID
import uuid, json

from db import get_db
from auth import get_current_user
from models import User, TelemetrySession, TelemetryEvent, CrashReport

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
    session = TelemetrySession(user_id=user.id)
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return {"session_id": session.id}


@router.post("/session/end/{session_id}")
async def end_session(
    session_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(TelemetrySession).where(TelemetrySession.id == session_id)
    )
    s = result.scalar_one_or_none()
    if s:
        s.is_active = False
        s.ended_at = datetime.utcnow()
        await db.commit()
    return {"status": "ended"}


@router.post("/event", response_model=EventOut)
async def post_event(
    payload: EventIn,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
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
        timestamp=payload.timestamp,
        crash_flagged=crash_detected
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)

    return {"event_id": event.id, "crash_detected": crash_detected}


@router.post("/false-alarm/{session_id}")
async def false_alarm(
    session_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """User said 'I'm fine' — unmark the crash flag."""
    result = await db.execute(
        select(TelemetryEvent)
        .where(
            TelemetryEvent.session_id == session_id,
            TelemetryEvent.crash_flagged == True
        )
        .order_by(TelemetryEvent.timestamp.desc())
        .limit(1)
    )
    event = result.scalar_one_or_none()
    if event:
        event.crash_flagged = False
        await db.commit()
    return {"status": "false_alarm_logged"}


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
        select(CrashReport).where(CrashReport.session_id == session_id)
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
