from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class TickerRead(BaseModel):
    id: int
    symbol: str
    name: str | None
    asset_type: str
    exchange: str | None
    currency: str
    is_active: bool

    model_config = {"from_attributes": True}


class PriceRead(BaseModel):
    price_date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    adjusted_close: Decimal | None
    volume: int

    model_config = {"from_attributes": True}


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


class EtlRunRequest(BaseModel):
    symbols: list[str] | None = None
    start_date: date | None = None
    end_date: date | None = None


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

    model_config = {"from_attributes": True}


class TopMoverRead(BaseModel):
    symbol: str
    metric_date: date
    daily_return: Decimal | None
    volume_ratio_20d: Decimal | None
    close: Decimal | None = None


class ReportGenerateRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=16)
    report_date: date | None = None
    report_type: str = "daily"


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

