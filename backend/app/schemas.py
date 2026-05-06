from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


Symbol = str
ReportTypeName = Literal["daily", "weekly", "monthly"]
EtlStatusName = Literal["pending", "running", "succeeded", "failed"]


def normalize_symbol(value: str) -> str:
    symbol = value.strip().upper()
    if not symbol:
        raise ValueError("Symbol cannot be empty")
    if len(symbol) > 16:
        raise ValueError("Symbol cannot exceed 16 characters")
    if not symbol.replace(".", "").replace("-", "").isalnum():
        raise ValueError("Symbol may contain only letters, numbers, dots, or hyphens")
    return symbol


class ErrorRead(BaseModel):
    detail: str


class HealthRead(BaseModel):
    status: str
    service: str = "capital-markets-api"
    environment: str


class TickerRead(BaseModel):
    id: int
    symbol: str
    name: str | None
    asset_type: str
    exchange: str | None
    currency: str
    is_active: bool

    model_config = {"from_attributes": True}


class TickerListRead(BaseModel):
    items: list[TickerRead]
    limit: int
    offset: int
    count: int


class PriceRead(BaseModel):
    price_date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    adjusted_close: Decimal | None
    volume: int

    model_config = {"from_attributes": True}


class MarketDataRead(BaseModel):
    symbol: str
    start_date: date | None
    end_date: date | None
    items: list[PriceRead]
    limit: int
    offset: int
    count: int


class MetricRead(BaseModel):
    metric_date: date
    daily_return: Decimal | None
    weekly_return: Decimal | None
    monthly_return: Decimal | None
    volatility_20d: Decimal | None
    sma_20: Decimal | None
    sma_50: Decimal | None
    ema_20: Decimal | None
    drawdown: Decimal | None
    volume_ratio_20d: Decimal | None

    model_config = {"from_attributes": True}


class MetricsRead(BaseModel):
    symbol: str
    items: list[MetricRead]
    limit: int
    offset: int
    count: int


class EtlRunRequest(BaseModel):
    symbols: list[Symbol] | None = Field(default=None, max_length=50)
    start_date: date | None = None
    end_date: date | None = None

    @field_validator("symbols")
    @classmethod
    def validate_symbols(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        normalized = [normalize_symbol(symbol) for symbol in value]
        deduped = list(dict.fromkeys(normalized))
        if not deduped:
            raise ValueError("At least one symbol is required when symbols are provided")
        return deduped

    @model_validator(mode="after")
    def validate_date_range(self) -> "EtlRunRequest":
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError("start_date must be before or equal to end_date")
        return self


class EtlJobRead(BaseModel):
    id: int
    job_type: str
    status: str
    symbols: list[str]
    started_at: datetime | None
    finished_at: datetime | None
    rows_extracted: int
    rows_loaded: int
    error_message: str | None
    metadata_json: dict[str, Any] | None

    model_config = {"from_attributes": True}


class EtlStatusRead(BaseModel):
    items: list[EtlJobRead]
    limit: int
    offset: int
    count: int
    status: EtlStatusName | None


class TopMoverRead(BaseModel):
    symbol: str
    metric_date: date
    daily_return: Decimal | None
    volume_ratio_20d: Decimal | None
    close: Decimal | None = None


class ReportGenerateRequest(BaseModel):
    symbol: Symbol = Field(min_length=1, max_length=16)
    report_date: date | None = None
    report_type: ReportTypeName = "daily"

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, value: str) -> str:
        return normalize_symbol(value)


class AiReportRead(BaseModel):
    id: int
    symbol: str
    report_date: date
    report_type: str
    summary: str
    trend_insights: list[str]
    anomaly_explanations: list[str]
    risk_notes: list[str]
    metrics_snapshot: dict[str, Any]
    model: str
    created_at: datetime
