from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from pydantic import BaseModel
from datetime import datetime
from uuid import UUID
import json

from db import get_db, session_local
from auth import get_current_user
from models import User, CrashReport, CrashSample
from agent.graph import blackbox_graph

router = APIRouter(prefix="/telemetry", tags=["telemetry"])

class CrashSampleIn(BaseModel):
    crash_report_id: UUID
    data: str
    timestamp: datetime
    is_pre_crash: bool = True

class ReportOut(BaseModel):
    id: UUID
    status: str
    severity: str
    summary: str | None
    location: str | None
    triggered_at: datetime
    created_at: datetime

class SampleOut(BaseModel):
    id: UUID
    crash_report_id: UUID
    data: str | None
    timestamp: datetime
    is_pre_crash: bool

@router.post("/sample", response_model=SampleOut)
async def add_sample(
    payload: CrashSampleIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    sample = CrashSample(
        crash_report_id=payload.crash_report_id,
        data=payload.data,
        timestamp=payload.timestamp,
        is_pre_crash=payload.is_pre_crash
    )
    db.add(sample)
    await db.commit()
    await db.refresh(sample)
    return sample

@router.post("/reconstruct/{report_id}")
async def reconstruct(
    report_id: UUID,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    background_tasks.add_task(_run_agent, str(report_id))
    return {"status": "reconstruction_started", "report_id": str(report_id)}

@router.get("/report/{report_id}", response_model=ReportOut)
async def get_report(
    report_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(CrashReport)
        .where(CrashReport.id == report_id)
        .order_by(desc(CrashReport.triggered_at))
        .limit(1)
    )
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(404, "Report not found")
    return report

@router.get("/reports")
async def list_reports(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(CrashReport)
        .order_by(CrashReport.triggered_at.desc())
    )
    reports = result.scalars().all()
    return [
        {
            "id": str(r.id),
            "status": r.status,
            "severity": r.severity,
            "summary": r.summary,
            "location": r.location,
            "triggered_at": r.triggered_at,
            "created_at": r.created_at,
        }
        for r in reports
    ]

@router.delete("/report/{report_id}")
async def delete_report(
    report_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(CrashReport).where(CrashReport.id == report_id)
    )
    report = result.scalar_one_or_none()
    if report:
        await db.delete(report)
        await db.commit()
    return {"status": "deleted"}

@router.post("/false-alarm/{report_id}")
async def false_alarm(
    report_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(CrashReport).where(CrashReport.id == report_id)
    )
    report = result.scalar_one_or_none()
    if report:
        report.status = "false_alarm"
        await db.commit()
    return {"status": "false_alarm_logged"}


async def _run_agent(report_id: str):
    print(f"[AGENT] Starting reconstruction for report {report_id}")
    async with session_local() as db:
        try:
            report_uuid = UUID(report_id)
            result = await db.execute(
                select(CrashSample)
                .where(CrashSample.crash_report_id == report_uuid)
                .order_by(CrashSample.timestamp.asc())
            )
            samples = result.scalars().all()
            print(f"[AGENT] Found {len(samples)} samples for report")

            if not samples:
                print(f"[AGENT] No samples found for report {report_id}")
                return

            events_data = []
            for s in samples:
                try:
                    parsed = json.loads(s.data) if s.data else {}
                except json.JSONDecodeError:
                    parsed = {}
                events_data.append({
                    "lat": parsed.get("lat", 0.0),
                    "lon": parsed.get("lon", 0.0),
                    "speed": parsed.get("speed", 0.0),
                    "accel": parsed.get("accel", 0.0),
                    "ax": parsed.get("ax", 0.0),
                    "ay": parsed.get("ay", 0.0),
                    "az": parsed.get("az", 0.0),
                    "timestamp": s.timestamp.isoformat(),
                })

            if not events_data:
                print(f"[AGENT] No valid event data for report {report_id}")
                return

            print(f"[AGENT] Invoking blackbox_graph agent with {len(events_data)} events")
            final_state = await blackbox_graph.ainvoke({
                "session_id": report_id,
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
            print(f"[AGENT] Agent complete. Severity: {final_state.get('severity', 'UNKNOWN')}")

            location = final_state.get("location_name", "")
            severity = final_state.get("severity", "UNKNOWN")
            summary = final_state.get("report", {}).get("summary", "")
            severity_score = final_state.get("severity_score", 0)

            result = await db.execute(
                select(CrashReport).where(CrashReport.id == report_uuid)
            )
            report = result.scalar_one_or_none()
            if report:
                report.status = severity.lower() if severity else "UNKNOWN"
                report.severity = severity
                report.summary = summary
                report.location = location
                report.triggered_at = datetime.utcnow()
                await db.commit()
                print(f"[AGENT] CrashReport updated to status={report.status}")

        except Exception as e:
            print(f"[AGENT] Error: {type(e).__name__}: {e}")
            import traceback; traceback.print_exc()
