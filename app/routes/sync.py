"""
HealthGuard Central Server – Sync Upload Endpoint.

Receives HMAC-signed vital-reading batches from edge nodes.
This is the endpoint that the edge node's sync_service.py calls.
"""

import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select, update, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database.database import get_db
from app.database.models import VitalReading, EdgeDevice, SyncLog

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/sync", tags=["Sync"])


def _verify_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Verify HMAC-SHA256 signature from the edge node."""
    expected = hmac.new(
        secret.encode("utf-8"),
        payload,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


@router.post("/upload")
async def receive_sync(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Receive a batch of vital readings from an edge node.

    Expected headers (sent by edge sync_service.py):
      - Authorization: Bearer <api_key>
      - X-Device-ID: <device_id>
      - X-Signature: <hmac_sha256_hex>
    """
    settings = get_settings()

    # ── 1. Authenticate via API key ──────────────────────────────────────
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
        )

    api_key = auth_header.removeprefix("Bearer ").strip()
    if api_key not in settings.api_keys_list:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key",
        )

    # ── 2. Verify HMAC signature ─────────────────────────────────────────
    raw_body = await request.body()
    signature = request.headers.get("X-Signature", "")

    if not _verify_signature(raw_body, signature, api_key):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid payload signature",
        )

    # ── 3. Parse payload ─────────────────────────────────────────────────
    try:
        data = json.loads(raw_body)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload",
        )

    device_id = request.headers.get("X-Device-ID", data.get("device_id", "unknown"))
    readings_data = data.get("readings", [])

    if not readings_data:
        return {"status": "ok", "records_received": 0, "message": "No readings in batch"}

    # ── 4. Store readings (skip duplicates by edge_uuid) ─────────────────
    stored = 0
    skipped = 0

    for r in readings_data:
        edge_uuid = r.get("uuid")
        if not edge_uuid:
            skipped += 1
            continue

        # Check for duplicate
        existing = await db.execute(
            select(VitalReading.id).where(VitalReading.edge_uuid == edge_uuid)
        )
        if existing.scalar_one_or_none() is not None:
            skipped += 1
            continue

        # Parse timestamp
        ts = None
        if r.get("timestamp"):
            try:
                ts = datetime.fromisoformat(r["timestamp"])
            except (ValueError, TypeError):
                ts = datetime.now(timezone.utc)

        vital = VitalReading(
            device_id=device_id,
            edge_uuid=edge_uuid,
            timestamp=ts or datetime.now(timezone.utc),
            heart_rate=r.get("heart_rate"),
            spo2=r.get("spo2"),
            temperature=r.get("temperature"),
            blood_pressure_sys=r.get("blood_pressure_sys"),
            blood_pressure_dia=r.get("blood_pressure_dia"),
            respiratory_rate=r.get("respiratory_rate"),
        )
        db.add(vital)
        stored += 1

    # ── 5. Update or create edge device record ───────────────────────────
    device_result = await db.execute(
        select(EdgeDevice).where(EdgeDevice.device_id == device_id)
    )
    device = device_result.scalar_one_or_none()

    if device:
        device.last_sync_at = datetime.now(timezone.utc)
        device.total_readings = (device.total_readings or 0) + stored
    else:
        db.add(EdgeDevice(
            device_id=device_id,
            last_sync_at=datetime.now(timezone.utc),
            total_readings=stored,
        ))

    # ── 6. Audit log ─────────────────────────────────────────────────────
    db.add(SyncLog(
        device_id=device_id,
        records_received=stored,
        status="success",
    ))

    await db.flush()

    logger.info(
        f"✅ Received {stored} readings from '{device_id}' "
        f"(skipped {skipped} duplicates)"
    )

    return {
        "status": "ok",
        "records_received": stored,
        "duplicates_skipped": skipped,
    }


@router.get("/devices")
async def list_devices(db: AsyncSession = Depends(get_db)):
    """List all registered edge devices and their sync status."""
    result = await db.execute(select(EdgeDevice).order_by(EdgeDevice.last_sync_at.desc()))
    devices = result.scalars().all()
    return [
        {
            "device_id": d.device_id,
            "label": d.label,
            "last_sync_at": d.last_sync_at.isoformat() if d.last_sync_at else None,
            "total_readings": d.total_readings,
            "registered_at": d.registered_at.isoformat() if d.registered_at else None,
        }
        for d in devices
    ]


@router.get("/stats")
async def sync_stats(db: AsyncSession = Depends(get_db)):
    """Overall sync statistics."""
    total_readings = (
        await db.execute(select(func.count(VitalReading.id)))
    ).scalar() or 0

    total_devices = (
        await db.execute(select(func.count(EdgeDevice.id)))
    ).scalar() or 0

    total_syncs = (
        await db.execute(select(func.count(SyncLog.id)))
    ).scalar() or 0

    return {
        "total_readings": total_readings,
        "total_devices": total_devices,
        "total_syncs": total_syncs,
    }


# ── Data Browsing Endpoints ────────────────────────────────────────────────


@router.get("/readings")
async def list_readings(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=200, description="Items per page"),
    device_id: str | None = Query(None, description="Filter by device ID"),
    db: AsyncSession = Depends(get_db),
):
    """Browse all synced vital readings (paginated)."""
    query = select(VitalReading)

    if device_id:
        query = query.where(VitalReading.device_id == device_id)

    # Total count
    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    # Paginated results
    query = query.order_by(desc(VitalReading.timestamp))
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    items = result.scalars().all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(1, -(-total // page_size)),
        "readings": [
            {
                "id": r.id,
                "device_id": r.device_id,
                "edge_uuid": r.edge_uuid,
                "timestamp": r.timestamp.isoformat() if r.timestamp else None,
                "received_at": r.received_at.isoformat() if r.received_at else None,
                "heart_rate": r.heart_rate,
                "spo2": r.spo2,
                "temperature": r.temperature,
                "blood_pressure_sys": r.blood_pressure_sys,
                "blood_pressure_dia": r.blood_pressure_dia,
                "respiratory_rate": r.respiratory_rate,
            }
            for r in items
        ],
    }


@router.get("/logs")
async def list_sync_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Browse the sync audit log – see when each device synced."""
    query = select(SyncLog).order_by(desc(SyncLog.timestamp))

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    items = result.scalars().all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "logs": [
            {
                "id": l.id,
                "device_id": l.device_id,
                "timestamp": l.timestamp.isoformat() if l.timestamp else None,
                "records_received": l.records_received,
                "status": l.status,
                "error_message": l.error_message,
            }
            for l in items
        ],
    }

