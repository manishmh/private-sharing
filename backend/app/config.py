"""Application settings, loaded from environment / backend/.env."""
import os
from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # PostgreSQL connection. Locally see .env.example for the supported forms;
    # managed hosts (Render etc.) inject a postgres:// URL — normalized below.
    database_url: str = "postgresql+psycopg://vault:vault@localhost:5432/vault"

    # Single shared admin password for this prototype only (NOT for production).
    admin_password: str = "changeme"

    # When true, /admin and /api/admin require HTTP Basic auth (user: admin,
    # pass: admin_password). Off locally; turned ON for the public deploy.
    admin_auth_enabled: bool = False

    # Where clean masters + watermarked caches live on disk.
    data_dir: str = "../data"

    # Path to the built frontend (frontend/dist). When set & present, FastAPI
    # serves the SPA same-origin in production. Empty = don't serve (dev uses Vite).
    static_dir: str = ""

    # Send the device-identity cookie only over HTTPS. Off locally (plain http),
    # ON in production (COOKIE_SECURE=true).
    cookie_secure: bool = False

    # Visible tiled watermark toggle. Disabled for now (the invisible LSB
    # forensic watermark is always applied regardless). Set WATERMARK_VISIBLE=true
    # to re-enable the visible tile — the rendering logic stays in watermark.py.
    watermark_visible: bool = False

    # Allowed CORS origins for the Vite dev server (unused when served same-origin).
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parent.parent / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("database_url", mode="after")
    @classmethod
    def _normalize_db_url(cls, v: str) -> str:
        # Managed hosts hand out driver-less postgres:// / postgresql:// URLs;
        # SQLAlchemy + psycopg v3 needs the explicit +psycopg suffix.
        if v.startswith("postgres://"):
            return "postgresql+psycopg://" + v[len("postgres://"):]
        if v.startswith("postgresql://"):
            return "postgresql+psycopg://" + v[len("postgresql://"):]
        return v

    @property
    def static_path(self) -> Path | None:
        return Path(self.static_dir).resolve() if self.static_dir else None

    @property
    def data_path(self) -> Path:
        # Resolve relative to the backend/ dir so run-location doesn't matter.
        base = Path(__file__).resolve().parent.parent
        return (base / self.data_dir).resolve()

    @property
    def masters_dir(self) -> Path:
        return self.data_path / "images" / "masters"

    @property
    def watermark_dir(self) -> Path:
        return self.data_path / "images" / "wm"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    # On Render (sets RENDER=true), a localhost DB URL means DATABASE_URL was never
    # injected — fail loudly with the fix instead of a cryptic psycopg traceback.
    if os.getenv("RENDER") and ("@localhost" in s.database_url or "127.0.0.1" in s.database_url):
        raise RuntimeError(
            "DATABASE_URL is not set on this Render service — it fell back to the local "
            "default (127.0.0.1). Fix: deploy via the render.yaml Blueprint (New > Blueprint), "
            "OR create a Render Postgres and add its Internal Connection String as the "
            "DATABASE_URL env var on this service, then redeploy."
        )
    # Ensure the image directories exist on startup.
    s.masters_dir.mkdir(parents=True, exist_ok=True)
    s.watermark_dir.mkdir(parents=True, exist_ok=True)
    return s


settings = get_settings()
