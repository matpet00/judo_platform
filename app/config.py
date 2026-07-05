from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "sqlite+aiosqlite:///./judo.db"

    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from: str | None = None
    smtp_use_tls: bool = True

    api_write_key: str | None = None
    jwt_secret: str = "dev-jwt-change-me"
    jwt_ttl_hours: int = 8
    pin_pepper: str = "dev-pin-pepper-change-me"
    allowed_origins: list[str] = ["http://127.0.0.1:5173", "http://localhost:5173"]
    upload_dir: str = "./uploads"
    max_upload_bytes: int = 10 * 1024 * 1024

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_allowed_origins(cls, v: object) -> object:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v


settings = Settings()
