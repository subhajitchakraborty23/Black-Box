from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Float, Boolean, UniqueConstraint
from db import Base
from datetime import datetime
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID as PGUUID
import uuid


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    clerk_id = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    name = Column(String)
    avatar_url = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

class Device(Base):
    __tablename__ = "devices"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    api_key_hash = Column(String, unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    label = Column(String, nullable=False)
    last_seen_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", backref="devices")

class CrashReport(Base):
    __tablename__ = "crash_reports"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id = Column(PGUUID(as_uuid=True), ForeignKey("devices.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(String, nullable=False, default="pending")
    triggered_at = Column(DateTime, nullable=False)
    severity = Column(String, nullable=True)
    summary = Column(Text, nullable=True)
    location_lat = Column(Float, nullable=True)
    location_lon = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    samples = relationship("CrashSample", backref="crash_report")

    __table_args__ = (
        UniqueConstraint("device_id", "triggered_at", name="uq_device_triggered"),
    )

class CrashSample(Base):
    __tablename__ = "crash_samples"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    crash_report_id = Column(PGUUID(as_uuid=True), ForeignKey("crash_reports.id"), nullable=False)
    t_offset_ms = Column(Integer, nullable=False)
    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)
    speed = Column(Float, nullable=False)
    ax = Column(Float, nullable=False)
    ay = Column(Float, nullable=False)
    az = Column(Float, nullable=False)
    gx = Column(Float, nullable=True)
    gy = Column(Float, nullable=True)
    gz = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class AlertLog(Base):
    __tablename__ = "alert_logs"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    crash_report_id = Column(PGUUID(as_uuid=True), ForeignKey("crash_reports.id"), nullable=False)
    channel = Column(String, nullable=False)
    recipient = Column(String, nullable=False)
    status = Column(String, nullable=False)
    sent_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
