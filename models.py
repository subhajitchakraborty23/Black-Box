from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Float, Boolean
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

class TelemetrySession(Base):
    __tablename__ = "telemetry_sessions"

    id = Column(PGUUID(as_uuid=True), primary_key=True,default=uuid.uuid4)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    started_at = Column(DateTime, default=datetime.utcnow)
    ended_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)

    user = relationship("User", backref="session")
    events = relationship("TelemetryEvent", backref="session")

class TelemetryEvent(Base):
    __tablename__ = "telemetry_events"

    id = Column(PGUUID(as_uuid=True), primary_key=True,default=uuid.uuid4)
    session_id = Column(PGUUID(as_uuid=True), ForeignKey("telemetry_sessions.id"), nullable=False)
    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)
    speed = Column(Float, nullable=False) 
    accel = Column(Float, nullable=False)
    ax = Column(Float, default=0.0)         
    ay = Column(Float, default=0.0)         
    az = Column(Float, default=0.0)  
    timestamp = Column(DateTime, nullable=False)
    crash_flagged = Column(Boolean, default=False)

class CrashReport(Base):
    __tablename__ = "crash_reports"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(PGUUID(as_uuid=True), ForeignKey("telemetry_sessions.id"), nullable=False)
    severity = Column(String, nullable=False)   
    report = Column(Text, nullable=True)        # JSON string from AI agent
    created_at = Column(DateTime, default=datetime.utcnow)