from pathlib import Path
import os
from typing import Literal

from dotenv import dotenv_values
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseModel):
    model_config = ConfigDict(frozen=True)
    data_dir: Path = PROJECT_ROOT / "data"
    sqlite_busy_timeout_ms: int = Field(default=5000, ge=1, le=60000)
    api_key: SecretStr = SecretStr("")
    max_document_bytes: int = Field(default=10 * 1024 * 1024, ge=1024, le=100 * 1024 * 1024)
    app_env: Literal['development', 'production'] = 'development'
    seed_demo_data: bool = False
    public_demo_enabled: bool = True
    public_demo_requests_per_minute: int = Field(default=60, ge=1, le=600)
    public_demo_global_requests_per_minute: int = Field(default=300, ge=1, le=3000)
    demo_execution_enabled: bool = True
    demo_max_runs: int = Field(default=50, ge=1, le=500)
    demo_run_ttl_hours: int = Field(default=24, ge=1, le=168)
    demo_storage_limit_mb: int = Field(default=128, ge=10, le=1024)

    @field_validator('seed_demo_data', 'public_demo_enabled', 'demo_execution_enabled', mode='before')
    @classmethod
    def seed_flag(cls, value):
        if isinstance(value, bool):
            return value
        if value not in ('0', '1'):
            raise ValueError('Flag must be 0 or 1')
        return value == '1'

    @field_validator("data_dir", mode="before")
    @classmethod
    def resolve_directory(cls, value):
        if str(value).strip() == "":
            raise ValueError("DATA_DIR cannot be blank")
        path = Path(value).expanduser()
        path = (path if path.is_absolute() else PROJECT_ROOT / path).resolve()
        if path == PROJECT_ROOT or path.is_relative_to(PROJECT_ROOT / "backend"):
            raise ValueError("DATA_DIR must be outside backend source folders")
        return path

    @property
    def database_path(self) -> Path:
        return self.data_dir / "transferiq.db"

    @classmethod
    def from_environment(cls):
        # Process environment overrides .env; never mutate the process environment.
        hosted = bool(os.environ.get('RAILWAY_ENVIRONMENT_ID')) or os.environ.get('RENDER') == 'true'
        local = {} if hosted else dotenv_values(PROJECT_ROOT / '.env')
        values = {**local, **os.environ}
        return cls(
            data_dir=values.get("DATA_DIR", PROJECT_ROOT / "data"),
            sqlite_busy_timeout_ms=values.get("SQLITE_BUSY_TIMEOUT_MS", 5000),
            api_key=values.get("API_KEY") or "",
            max_document_bytes=values.get("MAX_DOCUMENT_BYTES", 10 * 1024 * 1024),
            app_env=values.get('APP_ENV', 'development'),
            seed_demo_data=values.get('SEED_DEMO_DATA', '0'),
            public_demo_enabled=values.get('PUBLIC_DEMO_ENABLED', '1'),
            public_demo_requests_per_minute=values.get('PUBLIC_DEMO_REQUESTS_PER_MINUTE', 60),
            public_demo_global_requests_per_minute=values.get('PUBLIC_DEMO_GLOBAL_REQUESTS_PER_MINUTE', 300),
            demo_execution_enabled=values.get('DEMO_EXECUTION_ENABLED', '1'),
            demo_max_runs=values.get('DEMO_MAX_RUNS', 50),
            demo_run_ttl_hours=values.get('DEMO_RUN_TTL_HOURS', 24),
            demo_storage_limit_mb=values.get('DEMO_STORAGE_LIMIT_MB', 128),
        )
