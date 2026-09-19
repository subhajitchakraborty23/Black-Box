from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from datetime import datetime
from uuid import UUID
import json

from db import get_db, session_local
from auth.device import get_current_device
from models import Device, CrashReport, CrashSample
from agent.graph import blackbox_graph

router = APIRouter(prefix="/crash", tags=["crash"])

class CrashSamplePayload(BaseModel):
    t_offset_ms: int
    lat: float
    lon: float
    speed: float
    ax: float
    ay: float
    az: float
    gx: float | None = None
    gy: float | None = None
    gz: float | None = None

class CrashReportIn(BaseModel):
    triggered_at: str
    peak_accel_g: float
    delta_v_ms: float
    jerk_g_per_s: float
    samples: list[CrashSamplePayload]

class CrashReportOut(BaseModel):
    id: UUID
    status: str
    triggered_at: str
    created_at: datetime

async def _run_reconstruction(report_id: UUID):
    async with session_local() as db:
        try:
            result = await db.execute(
                select(CrashSample)
                .where(CrashSample.crash_report_id == report_id)
                .order_by(CrashSample.t_offset_ms.asc())
            )
            samples = result.scalars().all()
            if not samples:
                print(f"[RECON] No samples for report {report_id}")
                return

            events_data = []
            for s in samples:
                events_data.append({
                    "lat": s.lat,
                    "lon": s.lon,
                    "speed": s.speed,
                    "accel": (s.ax**2 + s.ay**2 + s.az**2) ** 0.5,
                    "ax": s.ax,
                    "ay": s.ay,
                    "az": s.az,
                    "timestamp": datetime.utcnow().isoformat(),
                })

            final_state = await blackbox_graph.ainvoke({
                "session_id": str(report_id),
                "events": events_data,
                "lat": samples[-1].lat if samples else 0.0,
                "lon": samples[-1].lon if samples else 0.0,
                "crash_speed": 0.0, "max_speed": 0.0, "peak_accel": 0.0,
                "peak_ax": 0.0, "peak_ay": 0.0, "peak_az": 0.0,
                "delta_vx": 0.0, "delta_vy": 0.0, "delta_vz": 0.0,
                "delta_v_total": 0.0,
                "collision_type": "UNKNOWN", "impact_angle": 0.0,
                "crash_idx": 0,
                "location_name": "", "weather": "", "speed_limit": "",
                "severity": "MINOR", "severity_score": 0, "report": {}
            })

            report_result = await db.execute(
                select(CrashReport).where(CrashReport.id == report_id)
            )
            report = report_result.scalar_one_or_none()
            if report:
                report.severity = final_state.get("severity", "UNKNOWN")
                report.summary = final_state.get("report", {}).get("summary", "")
                report.location_lat = samples[-1].lat if samples else None
                report.location_lon = samples[-1].lon if samples else None
                report.status = "completed"
                await db.commit()
                print(f"[RECON] Report {report_id} updated to {report.status}")

        except Exception as e:
            print(f"[RECON] Error: {e}")
            import traceback; traceback.print_exc()

@router.post("/report", response_model=CrashReportOut, status_code=status.HTTP_201_CREATED)
async def create_crash_report(
    payload: CrashReportIn,
    background_tasks: BackgroundTasks,
    device: Device = Depends(get_current_device),
    db: AsyncSession = Depends(get_db),
):
    triggered_at = datetime.fromisoformat(payload.triggered_at.replace("Z", "+00:00")).replace(tzinfo=None)

    crash_report = CrashReport(
        device_id=device.id,
        user_id=device.user_id,
        status="pending",
        triggered_at=triggered_at,
        severity=None,
        summary=None,
        location_lat=None,
        location_lon=None
    )
    db.add(crash_report)
    await db.commit()
    await db.refresh(crash_report)

    for sp in payload.samples:
        sample = CrashSample(
            crash_report_id=crash_report.id,
            t_offset_ms=sp.t_offset_ms,
            lat=sp.lat,
            lon=sp.lon,
            speed=sp.speed,
            ax=sp.ax,
            ay=sp.ay,
            az=sp.az,
            gx=sp.gx,
            gy=sp.gy,
            gz=sp.gz,
        )
        db.add(sample)
    await db.commit()

    background_tasks.add_task(_run_reconstruction, crash_report.id)

    return CrashReportOut(
        id=crash_report.id,
        status=crash_report.status,
        triggered_at=payload.triggered_at,
        created_at=crash_report.created_at
    )
