from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from auth import get_current_user
from db import get_db
from models import User


router = APIRouter(prefix="/users", tags=["users"])


class PushTokenUpdate(BaseModel):
    # Required but nullable: clients send null to unregister a device token.
    push_token: str | None


class PushTokenOut(BaseModel):
    push_token: str | None


@router.patch("/me", response_model=PushTokenOut)
async def update_my_push_token(
    payload: PushTokenUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user.push_token = payload.push_token
    await db.commit()
    await db.refresh(user)
    return PushTokenOut(push_token=user.push_token)
