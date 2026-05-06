from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class EtlStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class Ticker(Base):
    __tablename__ = "tickers"

    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    name: Mapped[str | None] = mapped_column(String(255))
    asset_type: Mapped[str] = mapped_column(String(32), default="equity")
    exchange: Mapped[str | None] = mapped_column(String(32))
    currency: Mapped[str] = mapped_column(String(8), default="USD")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    prices: Mapped[list["HistoricalPrice"]] = relationship(back_populates="ticker")
    metrics: Mapped[list["ComputedMetric"]] = relationship(back_populates="ticker")
    reports: Mapped[list["AiReport"]] = relationship(back_populates="ticker")


class HistoricalPrice(Base):
    __tablename__ = "historical_prices"
    __table_args__ = (
        UniqueConstraint("ticker_id", "price_date", "source", name="uq_price_ticker_date_source"),
        Index("ix_prices_ticker_date", "ticker_id", "price_date"),
        Index("ix_prices_date", "price_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    ticker_id: Mapped[int] = mapped_column(ForeignKey("tickers.id", ondelete="CASCADE"))
    price_date: Mapped[date] = mapped_column(Date)
    open: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    high: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    low: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    close: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    adjusted_close: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    volume: Mapped[int] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String(32), default="stooq")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    ticker: Mapped[Ticker] = relationship(back_populates="prices")


class ComputedMetric(Base):
    __tablename__ = "computed_metrics"
    __table_args__ = (
        UniqueConstraint("ticker_id", "metric_date", name="uq_metric_ticker_date"),
        Index("ix_metrics_ticker_date", "ticker_id", "metric_date"),
        Index("ix_metrics_date_return", "metric_date", "daily_return"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    ticker_id: Mapped[int] = mapped_column(ForeignKey("tickers.id", ondelete="CASCADE"))
    metric_date: Mapped[date] = mapped_column(Date)
    daily_return: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))
    weekly_return: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))
    monthly_return: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))
    volatility_20d: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))
    sma_20: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    sma_50: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    ema_20: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    drawdown: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))
    volume_ratio_20d: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    ticker: Mapped[Ticker] = relationship(back_populates="metrics")


class AiReport(Base):
    __tablename__ = "ai_reports"
    __table_args__ = (
        Index("ix_reports_ticker_date", "ticker_id", "report_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    ticker_id: Mapped[int] = mapped_column(ForeignKey("tickers.id", ondelete="CASCADE"))
    report_date: Mapped[date] = mapped_column(Date)
    report_type: Mapped[str] = mapped_column(String(32), default="daily")
    summary: Mapped[str] = mapped_column(Text)
    trend_insights: Mapped[list[str]] = mapped_column(JSON)
    anomaly_explanations: Mapped[list[str]] = mapped_column(JSON)
    risk_notes: Mapped[list[str]] = mapped_column(JSON)
    metrics_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON)
    model: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    ticker: Mapped[Ticker] = relationship(back_populates="reports")


class EtlJob(Base):
    __tablename__ = "etl_jobs"
    __table_args__ = (
        Index("ix_etl_jobs_started_status", "started_at", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    job_type: Mapped[str] = mapped_column(String(32), default="market_data")
    status: Mapped[str] = mapped_column(String(32), default=EtlStatus.PENDING.value)
    symbols: Mapped[list[str]] = mapped_column(JSON)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rows_extracted: Mapped[int] = mapped_column(Integer, default=0)
    rows_loaded: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

