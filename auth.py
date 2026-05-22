from fastapi import Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import httpx, os
from jose import jwt, JWTError
from db import get_db
from models import User

_jwks_cache = None

async def _get_jwks():
    global _jwks_cache
    if _jwks_cache:
        return _jwks_cache
    jwks_url = os.getenv("CLERK_JWKS_URL")
    async with httpx.AsyncClient() as c:
        r = await c.get(jwks_url)
        _jwks_cache = r.json()
    return _jwks_cache

async def get_current_user(
    authorization: str = Header(...),
    db: AsyncSession = Depends(get_db)
) -> User:
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing Bearer token")
    token = authorization.removeprefix("Bearer ")
    try:
        jwks = await _get_jwks()
        payload = jwt.decode(token, jwks, algorithms=["RS256"])
        clerk_id: str = payload["sub"]
    except JWTError as e:
        raise HTTPException(401, f"Invalid token: {e}")

    result = await db.execute(select(User).where(User.clerk_id == clerk_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not synced yet — webhook may be pending")
    return user