"""Environment configuration. Importing the app never connects to a provider."""
from functools import lru_cache
from pathlib import Path
import re
from typing import Literal
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=Path(__file__).resolve().parents[1]/'.env', extra='ignore', case_sensitive=False)
    app_env: Literal['development','test','preview','production'] = 'development'
    database_url: str = ''
    migration_database_url: str = ''
    postgis_schema: str = 'public'
    app_origins: list[str] = ['http://localhost:5173']
    cookie_secure: bool = False
    csrf_secret: str = ''
    rate_limit_secret: str = ''
    trust_vercel_proxy: bool = False
    db_pool_size: int = Field(1, ge=1, le=5)
    aws_region: str = 'us-west-2'
    aws_access_key_id: str = ''
    aws_secret_access_key: str = ''
    s3_bucket: str = ''
    openai_api_key: str = ''
    openai_realtime_model: str = ''
    openai_transcription_model: str = ''
    openai_extract_model: str = ''
    openai_voice: str = 'marin'
    ai_request_timeout_seconds: float = Field(45, ge=1, le=45)
    max_recording_bytes: int = Field(26214400, ge=1, le=26214400)
    max_recording_duration_ms: int = Field(600000, ge=1, le=600000)

    @field_validator('postgis_schema')
    @classmethod
    def schema_name(cls, value):
        if not re.fullmatch(r'[a-z_][a-z0-9_]{0,62}', value):
            raise ValueError('POSTGIS_SCHEMA must be a simple PostgreSQL identifier.')
        return value

    @field_validator('app_origins')
    @classmethod
    def origins(cls, values):
        from urllib.parse import urlsplit
        for value in values:
            part=urlsplit(value)
            if part.scheme not in ('http','https') or not part.netloc or part.path or part.query or part.fragment or '*' in value or part.username:
                raise ValueError('APP_ORIGINS must contain exact browser origins without paths or wildcards.')
        return values

    @property
    def cookie_name(self):
        return '__Host-farm_session' if self.cookie_secure else 'farm_session'

@lru_cache
def settings():
    return Settings()
