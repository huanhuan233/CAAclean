from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    app_host: str = "0.0.0.0"
    app_port: int = 8000
    cors_origins: str = "http://localhost:9527,http://localhost:5173"

    database_url_value: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("DATABASE_URL", "database_url", "database_url_value"),
    )
    postgres_host: str = "127.0.0.1"
    postgres_port: int = 5432
    postgres_user: str = "postgres"
    postgres_password: str = ""
    postgres_db: str = "postgres"

    freecad_cmd: str = "freecadcmd"
    freecad_timeout: int = 600
    cad_script_dir: Path = Path("backend/freecad_scripts")
    cad_work_dir: Path = Path("cad-work")
    cad_max_upload_mb: int = 200
    cad_max_concurrency: int = 1
    cad_mesh_deflection: float = 0.1
    cad_stale_job_minutes: int = 30

    @property
    def database_url(self) -> str:
        if self.database_url_value:
            if self.database_url_value.startswith("postgresql://"):
                return self.database_url_value.replace("postgresql://", "postgresql+asyncpg://", 1)
            return self.database_url_value
        url = URL.create(
            drivername="postgresql+asyncpg",
            username=self.postgres_user,
            password=self.postgres_password,
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
        )
        return url.render_as_string(hide_password=False)

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
