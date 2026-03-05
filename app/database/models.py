"""
HealthGuard Central Server – Database Models.

Stores vital readings received from edge nodes.
"""

from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
)

from app.database.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class VitalReading(Base):
    """Vital readings synced from edge nodes."""

    __tablename__ = "vital_readings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(String(50), nullable=False, index=True)
    edge_uuid = Column(String(36), unique=True, nullable=False)
    timestamp = Column(DateTime(timezone=True), default=_utcnow, index=True)
    received_at = Column(DateTime(timezone=True), default=_utcnow)

    # Vital signs
    heart_rate = Column(Float, nullable=True)
    spo2 = Column(Float, nullable=True)
    temperature = Column(Float, nullable=True)
    blood_pressure_sys = Column(Float, nullable=True)
    blood_pressure_dia = Column(Float, nullable=True)
    respiratory_rate = Column(Float, nullable=True)


class EdgeDevice(Base):
    """Registered edge node devices."""

    __tablename__ = "edge_devices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(String(50), unique=True, nullable=False, index=True)
    label = Column(String(100), nullable=True)
    last_sync_at = Column(DateTime(timezone=True), nullable=True)
    total_readings = Column(Integer, default=0)
    registered_at = Column(DateTime(timezone=True), default=_utcnow)


class SyncLog(Base):
    """Audit trail of sync uploads received."""

    __tablename__ = "sync_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(String(50), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), default=_utcnow)
    records_received = Column(Integer, default=0)
    status = Column(String(20), nullable=False)
    error_message = Column(Text, nullable=True)
