from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    log_level: str = "INFO"
    database_url: str = Field(default="postgresql+psycopg://capital:capital@localhost:5432/capital_markets")
    db_pool_size: int = Field(default=5, ge=1)
    db_max_overflow: int = Field(default=10, ge=0)
    db_pool_timeout: int = Field(default=30, ge=1)
    backend_cors_origins: str = "http://localhost:3000"
    market_data_provider: str = "stooq"
    market_data_timeout_seconds: float = Field(default=30.0, gt=0)
    market_data_retries: int = Field(default=2, ge=0, le=5)
    stooq_api_key: str | None = None
    alpha_vantage_api_key: str | None = None
    default_symbols: str = "AAPL,MSFT,SPY,TSLA,NVDA,JPM"
    ai_provider: str = "openai"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.backend_cors_origins.split(",") if origin.strip()]

    @property
    def default_symbol_list(self) -> list[str]:
        return [symbol.strip().upper() for symbol in self.default_symbols.split(",") if symbol.strip()]

    @property
    def is_development(self) -> bool:
        return self.app_env.lower() in {"local", "development", "dev"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
