from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import ComputedMetric, HistoricalPrice, Ticker


@dataclass(frozen=True)
class PriceLoadResult:
    ticker: Ticker
    rows_submitted: int


@dataclass(frozen=True)
class MetricLoadResult:
    ticker: Ticker
    rows_submitted: int


@dataclass(frozen=True)
class TickerListResult:
    items: list[Ticker]
    total: int


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _decimal(value: object) -> Decimal | None:
    if value is None or pd.isna(value):
        return None
    return Decimal(str(value))


def upsert_ticker(db: Session, symbol: str, asset_type: str = "equity") -> Ticker:
    normalized_symbol = symbol.strip().upper()
    stmt = insert(Ticker).values(
        symbol=normalized_symbol,
        name=normalized_symbol,
        asset_type=asset_type,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[Ticker.symbol],
        set_={"updated_at": _utc_now(), "is_active": True},
    ).returning(Ticker.id)
    ticker_id = db.execute(stmt).scalar_one()
    ticker = db.get(Ticker, ticker_id)
    if ticker is None:
        raise RuntimeError(f"Ticker upsert failed for {normalized_symbol}")
    return ticker


def list_tickers(
    db: Session,
    *,
    search: str | None = None,
    active_only: bool = True,
    limit: int = 50,
    offset: int = 0,
) -> TickerListResult:
    filters = []
    if active_only:
        filters.append(Ticker.is_active.is_(True))
    if search:
        filters.append(Ticker.symbol.ilike(f"%{search.strip().upper()}%"))

    query = select(Ticker)
    count_query = select(func.count()).select_from(Ticker)
    if filters:
        query = query.where(*filters)
        count_query = count_query.where(*filters)

    items = list(db.execute(query.order_by(Ticker.symbol).limit(limit).offset(offset)).scalars())
    total = db.execute(count_query).scalar_one()
    return TickerListResult(items=items, total=total)


def upsert_historical_prices(db: Session, ticker: Ticker, prices: pd.DataFrame) -> PriceLoadResult:
    rows = [
        {
            "ticker_id": ticker.id,
            "price_date": row.price_date,
            "open": _decimal(row.open),
            "high": _decimal(row.high),
            "low": _decimal(row.low),
            "close": _decimal(row.close),
            "adjusted_close": _decimal(row.adjusted_close),
            "volume": int(row.volume),
            "source": row.source,
        }
        for row in prices.itertuples(index=False)
    ]
    if not rows:
        return PriceLoadResult(ticker=ticker, rows_submitted=0)

    stmt = insert(HistoricalPrice).values(rows)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_price_ticker_date_source",
        set_={
            "open": stmt.excluded.open,
            "high": stmt.excluded.high,
            "low": stmt.excluded.low,
            "close": stmt.excluded.close,
            "adjusted_close": stmt.excluded.adjusted_close,
            "volume": stmt.excluded.volume,
            "updated_at": _utc_now(),
        },
    )
    db.execute(stmt)
    return PriceLoadResult(ticker=ticker, rows_submitted=len(rows))


def load_ticker_prices(db: Session, symbol: str, prices: pd.DataFrame) -> PriceLoadResult:
    ticker = upsert_ticker(db, symbol)
    return upsert_historical_prices(db, ticker, prices)


def upsert_computed_metrics(db: Session, ticker: Ticker, metrics: pd.DataFrame) -> MetricLoadResult:
    persistable_columns = [
        "metric_date",
        "daily_return",
        "weekly_return",
        "monthly_return",
        "volatility_20d",
        "sma_20",
        "sma_50",
        "ema_20",
        "drawdown",
        "volume_ratio_20d",
    ]
    missing = set(persistable_columns).difference(metrics.columns)
    if missing:
        raise ValueError(f"Missing computed metric columns: {sorted(missing)}")

    rows = [
        {
            "ticker_id": ticker.id,
            "metric_date": row.metric_date,
            "daily_return": row.daily_return,
            "weekly_return": row.weekly_return,
            "monthly_return": row.monthly_return,
            "volatility_20d": row.volatility_20d,
            "sma_20": row.sma_20,
            "sma_50": row.sma_50,
            "ema_20": row.ema_20,
            "drawdown": row.drawdown,
            "volume_ratio_20d": row.volume_ratio_20d,
        }
        for row in metrics[persistable_columns].itertuples(index=False)
    ]
    if not rows:
        return MetricLoadResult(ticker=ticker, rows_submitted=0)

    stmt = insert(ComputedMetric).values(rows)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_metric_ticker_date",
        set_={
            "daily_return": stmt.excluded.daily_return,
            "weekly_return": stmt.excluded.weekly_return,
            "monthly_return": stmt.excluded.monthly_return,
            "volatility_20d": stmt.excluded.volatility_20d,
            "sma_20": stmt.excluded.sma_20,
            "sma_50": stmt.excluded.sma_50,
            "ema_20": stmt.excluded.ema_20,
            "drawdown": stmt.excluded.drawdown,
            "volume_ratio_20d": stmt.excluded.volume_ratio_20d,
            "updated_at": _utc_now(),
        },
    )
    db.execute(stmt)
    return MetricLoadResult(ticker=ticker, rows_submitted=len(rows))
