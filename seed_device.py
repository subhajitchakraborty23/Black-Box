import asyncio, hashlib, uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from db import engine, session_local, Base
from models import User, Device

async def seed():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_local() as db:
        result = await db.execute(select(User))
        users = result.scalars().all()
        if not users:
            print("No users found. Create one first via webhook sync.")
            return

        user = users[0]
        api_key = "demo-api-key-2025"
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()

        device = Device(
            id=uuid.uuid4(),
            api_key_hash=key_hash,
            user_id=user.id,
            label="demo-unit"
        )
        db.add(device)
        await db.commit()
        await db.refresh(device)
        print(f"Seeded device: id={device.id}, user_id={device.user_id}, label={device.label}")
        print(f"API key to use: {api_key}")

asyncio.run(seed())
