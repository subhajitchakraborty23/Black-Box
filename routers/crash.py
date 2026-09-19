from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from datetime import datetime
from uuid import UUID
import json
import os
import httpx

from db import get_db, session_local
from auth import get_current_user
from auth.device import get_current_device
from models import Device, User, CrashReport, CrashSample, AlertLog
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


class CrashReportRead(BaseModel):
    id: UUID
    device_id: UUID
    status: str
    triggered_at: datetime
    created_at: datetime
    severity: str | None
    summary: str | None
    location_lat: float | None
    location_lon: float | None


def _serialize_report(report: CrashReport) -> CrashReportRead:
    return CrashReportRead(
        id=report.id,
        device_id=report.device_id,
        status=report.status,
        triggered_at=report.triggered_at,
        created_at=report.created_at,
        severity=report.severity,
        summary=report.summary,
        location_lat=report.location_lat,
        location_lon=report.location_lon,
    )


async def _send_push_alert(
    db: AsyncSession,
    report: CrashReport,
    user: User,
    final_state: dict,
) -> None:
    """Send the reconstructed crash alert to the user's registered push token."""
    push_token = (user.push_token or "").strip()
    if not push_token:
        print(f"[ALERT] No push token for user {user.id}; skipping report {report.id}")
        db.add(AlertLog(
            crash_report_id=report.id,
            channel="push",
            recipient="unregistered",
            status="skipped",
        ))
        await db.commit()
        return

    report_data = final_state.get("report") or {}
    message = {
        "to": push_token,
        "title": "Crash detected",
        "body": report_data.get("summary") or "A crash report has been reconstructed.",
        "data": {
            "report_id": str(report.id),
            "severity": report.severity or "UNKNOWN",
            "latitude": report.location_lat,
            "longitude": report.location_lon,
        },
    }
    endpoint = os.getenv("PUSH_SERVICE_URL", "https://exp.host/--/api/v2/push/send")
    status_value = "failed"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(endpoint, json=message)
            response.raise_for_status()
            provider_result = response.json()
            provider_data = provider_result.get("data", {})
            if provider_data.get("status") == "error":
                raise RuntimeError(provider_data.get("message", "push provider rejected message"))
        status_value = "sent"
        print(f"[ALERT] Push sent for report {report.id}")
    except Exception as exc:
        print(f"[ALERT] Push failed for report {report.id}: {type(exc).__name__}: {exc}")

    db.add(AlertLog(
        crash_report_id=report.id,
        channel="push",
        recipient=push_token,
        status=status_value,
        sent_at=datetime.utcnow() if status_value == "sent" else None,
    ))
    await db.commit()

async def _run_reconstruction(
    report_id: UUID,
    peak_accel_g: float,
    delta_v_ms: float,
    jerk_g_per_s: float,
):
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
                # These are the ESP32's trigger-time measurements. Preserve them
                # for reconstruction instead of deriving replacements from the
                # sampled window.
                "peak_accel_g": peak_accel_g,
                "delta_v_ms": delta_v_ms,
                "jerk_g_per_s": jerk_g_per_s,
            })

            report_result = await db.execute(
                select(CrashReport).where(CrashReport.id == report_id)
            )
            report = report_result.scalar_one_or_none()
            if report:
                report.severity = final_state.get("severity", "UNKNOWN")
                report.summary = final_state.get("report", {}).get("summary", "")
                if not report.summary.strip():
                    print(
                        f"[RECON] Warning: reconstruction for report {report_id} "
                        "returned an empty summary"
                    )
                report.location_lat = samples[-1].lat if samples else None
                report.location_lon = samples[-1].lon if samples else None
                if report.status != "false_alarm":
                    report.status = "completed"
                await db.commit()
                print(f"[RECON] Report {report_id} updated to {report.status}")

                if report.status == "completed":
                    user_result = await db.execute(
                        select(User).where(User.id == report.user_id)
                    )
                    user = user_result.scalar_one_or_none()
                    if user:
                        await _send_push_alert(db, report, user, final_state)
                    else:
                        print(f"[ALERT] User {report.user_id} not found for report {report_id}")

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

    background_tasks.add_task(
        _run_reconstruction,
        crash_report.id,
        payload.peak_accel_g,
        payload.delta_v_ms,
        payload.jerk_g_per_s,
    )

    return CrashReportOut(
        id=crash_report.id,
        status=crash_report.status,
        triggered_at=payload.triggered_at,
        created_at=crash_report.created_at
    )


@router.get("/reports", response_model=list[CrashReportRead])
async def list_crash_reports(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(CrashReport)
        .where(CrashReport.user_id == user.id)
        .order_by(CrashReport.triggered_at.desc())
    )
    return [_serialize_report(report) for report in result.scalars().all()]


@router.get("/reports/{report_id}", response_model=CrashReportRead)
async def get_crash_report(
    report_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(CrashReport).where(
            CrashReport.id == report_id,
            CrashReport.user_id == user.id,
        )
    )
    report = result.scalar_one_or_none()
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Crash report not found")
    return _serialize_report(report)


@router.post("/reports/{report_id}/false-alarm", response_model=CrashReportRead)
async def mark_false_alarm(
    report_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(CrashReport).where(
            CrashReport.id == report_id,
            CrashReport.user_id == user.id,
        )
    )
    report = result.scalar_one_or_none()
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Crash report not found")

    report.status = "false_alarm"
    await db.commit()
    await db.refresh(report)
    return _serialize_report(report)
