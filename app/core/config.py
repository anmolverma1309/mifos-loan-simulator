"""
Application configuration using Pydantic Settings.
All values can be overridden via environment variables or .env file.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # App
    APP_NAME: str = "Mifos Loan Amortisation Simulator"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    CACHE_TTL_SECONDS: int = 3600  # 1 hour default

    # Mifos X Fineract API (optional — for live loan fetch)
    FINERACT_BASE_URL: str = "https://demo.fineract.dev/fineract-provider/api/v1"
    FINERACT_USERNAME: str = "mifos"
    FINERACT_PASSWORD: str = "password"
    FINERACT_TENANT: str = "default"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )


settings = Settings()
