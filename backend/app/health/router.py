# 提供 API 存活与数据库连通性探测，不执行模型解析或 CATIA 许可证验证。
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session


router = APIRouter(prefix="/api/health", tags=["health"])


# 确认当前 API 能正常响应。
@router.get("")
async def health() -> dict[str, bool]:
    return {"ok": True}


# 在当前会话执行轻量 SQL，数据库异常交由请求错误处理通路返回。
@router.get("/database")
async def database_health(session: AsyncSession = Depends(get_session)) -> dict[str, bool]:
    await session.execute(text("select 1"))
    return {"ok": True}
