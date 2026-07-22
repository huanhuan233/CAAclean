from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.cad.router import router as cad_router
from app.cad.service import recover_interrupted_revisions
from app.core.config import get_settings
from app.db.session import init_db
from app.health.router import router as health_router


settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    if app.state.init_database_on_startup:
        await init_db()
    await recover_interrupted_revisions(settings)
    yield


app = FastAPI(title="STEP/CAD 3D Parser", lifespan=lifespan)
app.state.init_database_on_startup = True
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(health_router)
app.include_router(cad_router)
