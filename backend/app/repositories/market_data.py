from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal

import pandas as pd
from sqlalchemy import desc, func, select
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


@dataclass(frozen=True)
class PriceHistoryResult:
    ticker: Ticker | None
    items: list[HistoricalPrice]
    total: int


@dataclass(frozen=True)
class MetricHistoryResult:
    ticker: Ticker | None
    items: list[ComputedMetric]
    total: int


@dataclass(frozen=True)
class TopMoverRecord:
    symbol: str
    metric_date: date
    daily_return: Decimal | None
    volume_ratio_20d: Decimal | None


@dataclass(frozen=True)
class TopMoversResult:
    items: list[TopMoverRecord]
    metric_date: date | None
    direction: str


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


def get_ticker_by_symbol(db: Session, symbol: str) -> Ticker | None:
    return db.execute(select(Ticker).where(Ticker.symbol == symbol.strip().upper())).scalar_one_or_none()


def list_historical_prices(
    db: Session,
    *,
    symbol: str,
    start_date: date | None = None,
    end_date: date | None = None,
    limit: int = 252,
    offset: int = 0,
) -> PriceHistoryResult:
    ticker = get_ticker_by_symbol(db, symbol)
    if ticker is None:
        return PriceHistoryResult(ticker=None, items=[], total=0)

    filters = [HistoricalPrice.ticker_id == ticker.id]
    if start_date:
        filters.append(HistoricalPrice.price_date >= start_date)
    if end_date:
        filters.append(HistoricalPrice.price_date <= end_date)

    query = select(HistoricalPrice).where(*filters)
    count_query = select(func.count()).select_from(HistoricalPrice).where(*filters)
    items = list(
        db.execute(
            query.order_by(HistoricalPrice.price_date).limit(limit).offset(offset)
        ).scalars()
    )
    total = db.execute(count_query).scalar_one()
    return PriceHistoryResult(ticker=ticker, items=items, total=total)


def list_computed_metrics(
    db: Session,
    *,
    symbol: str,
    start_date: date | None = None,
    end_date: date | None = None,
    limit: int = 252,
    offset: int = 0,
) -> MetricHistoryResult:
    ticker = get_ticker_by_symbol(db, symbol)
    if ticker is None:
        return MetricHistoryResult(ticker=None, items=[], total=0)

    filters = [ComputedMetric.ticker_id == ticker.id]
    if start_date:
        filters.append(ComputedMetric.metric_date >= start_date)
    if end_date:
        filters.append(ComputedMetric.metric_date <= end_date)

    query = select(ComputedMetric).where(*filters)
    count_query = select(func.count()).select_from(ComputedMetric).where(*filters)
    items = list(
        db.execute(
            query.order_by(ComputedMetric.metric_date).limit(limit).offset(offset)
        ).scalars()
    )
    total = db.execute(count_query).scalar_one()
    return MetricHistoryResult(ticker=ticker, items=items, total=total)


def list_top_movers(
    db: Session,
    *,
    metric_date: date | None = None,
    direction: str = "gainers",
    limit: int = 10,
) -> TopMoversResult:
    resolved_date = metric_date
    if resolved_date is None:
        resolved_date = db.execute(
            select(ComputedMetric.metric_date).order_by(desc(ComputedMetric.metric_date))
        ).scalar_one_or_none()
    if resolved_date is None:
        return TopMoversResult(items=[], metric_date=None, direction=direction)

    order_column = desc(ComputedMetric.daily_return) if direction == "gainers" else ComputedMetric.daily_return
    rows = db.execute(
        select(
            Ticker.symbol,
            ComputedMetric.metric_date,
            ComputedMetric.daily_return,
            ComputedMetric.volume_ratio_20d,
        )
        .join(ComputedMetric, ComputedMetric.ticker_id == Ticker.id)
        .where(ComputedMetric.metric_date == resolved_date)
        .where(ComputedMetric.daily_return.is_not(None))
        .order_by(order_column)
        .limit(limit)
    ).all()

    items = [
        TopMoverRecord(
            symbol=row[0],
            metric_date=row[1],
            daily_return=row[2],
            volume_ratio_20d=row[3],
        )
        for row in rows
    ]
    return TopMoversResult(items=items, metric_date=resolved_date, direction=direction)


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
