
"""
Application settings — loaded from environment variables / .env file.
All values have safe defaults for local development.
"""

from __future__ import annotations

from functools import lru_cache
from typing import List
import os

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ────────────────────────────────────────────────────────────────────
    APP_NAME: str = "Digital Ecosystem Platform"
    APP_VERSION: str = "2.0.0"
    DEBUG: bool = False

    # ── Database ───────────────────────────────────────────────────────────────
    # SQLite (dev) or postgresql+asyncpg://user:pass@host/db (prod)
    DATABASE_URL: str = "sqlite+aiosqlite:///./dep_platform.db"

    # ── Security ───────────────────────────────────────────────────────────────
    SECRET_KEY: str = os.environ.get('JWT_SECRET_KEY', "CHANGE-ME-IN-PRODUCTION-use-openssl-rand-hex-32")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ── CORS ───────────────────────────────────────────────────────────────────
    CORS_ORIGINS: List[str] = ["http://localhost:8501", "http://localhost:3000"]

    # ── Event Bus ─────────────────────────────────────────────────────────────
    # Set to "redis" to use Redis; defaults to "memory"
    EVENT_BUS_BACKEND: str = "memory"
    REDIS_URL: str = "redis://localhost:6379"

    # ── MQTT ──────────────────────────────────────────────────────────────────
    MQTT_BROKER_HOST: str = "localhost"
    MQTT_BROKER_PORT: int = 1883
    MQTT_USERNAME: str = ""
    MQTT_PASSWORD: str = ""
    MQTT_ENABLED: bool = False

    # ── OPC-UA ────────────────────────────────────────────────────────────────
    OPCUA_ENDPOINT: str = "opc.tcp://localhost:4840"
    OPCUA_ENABLED: bool = False

    # ── External simulated sources ─────────────────────────────────────────────
    FACTORY_SIMULATOR_URL: str = "http://localhost:9100"

    # ── Logging ───────────────────────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"

    # ── Pagination ────────────────────────────────────────────────────────────
    DEFAULT_PAGE_SIZE: int = 50
    MAX_PAGE_SIZE: int = 500

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _parse_cors(cls, v):
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
