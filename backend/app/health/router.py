from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session


router = APIRouter(prefix="/api/health", tags=["health"])


@router.get("")
async def health() -> dict[str, bool]:
    return {"ok": True}


@router.get("/database")
async def database_health(session: AsyncSession = Depends(get_session)) -> dict[str, bool]:
    await session.execute(text("select 1"))
    return {"ok": True}
