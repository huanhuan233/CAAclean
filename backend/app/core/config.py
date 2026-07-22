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
    drawing_layout_provider: str = "auto"
    mineru_layout_mode: str = "disabled"
    mineru_layout_url: str = ""
    mineru_layout_command: str = ""
    mineru_layout_timeout: int = 180
    drawing_max_image_mb: int = 20
    drawing_max_side: int = 4096
    drawing_inference_max_side: int = 2048
    drawing_crop_padding_ratio: float = 0.03
    drawing_table_padding_ratio: float = 0.02
    drawing_diagram_padding_ratio: float = 0.05
    drawing_region_min_area_ratio: float = 0.003
    drawing_region_merge_gap_ratio: float = 0.02
    cad_spec_work_dir: Path = Path("cad-spec-work")
    vision_binding: str = "openai"
    vision_model: str = ""
    vision_binding_host: str = ""
    vision_binding_api_key: str = ""
    vision_enable_thinking: bool = False
    vision_extra_body: str = ""
    ai_request_timeout: int = 600
    ai_max_retries: int = 2

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
