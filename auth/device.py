from fastapi import Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import hashlib
from db import get_db
from models import Device

async def get_current_device(
    x_api_key: str = Header(...),
    db: AsyncSession = Depends(get_db)
) -> Device:
    key_hash = hashlib.sha256(x_api_key.encode()).hexdigest()
    try:
        result = await db.execute(select(Device).where(Device.api_key_hash == key_hash))
        device = result.scalar_one_or_none()
        if not device:
            raise HTTPException(401, "Invalid API key")
        return device
    except Exception as e:
        print(f"Database error in get_current_device: {e}")
        raise HTTPException(500, "Database connection error. Please try again.")
