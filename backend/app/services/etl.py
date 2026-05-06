import logging
from datetime import UTC, date, datetime
from decimal import Decimal

import pandas as pd
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models import ComputedMetric, EtlJob, EtlStatus, HistoricalPrice, Ticker
from app.services.analytics import compute_metrics
from app.services.market_data import get_market_data_provider

logger = logging.getLogger(__name__)


def _clean_prices(frame: pd.DataFrame) -> pd.DataFrame:
    required = ["price_date", "open", "high", "low", "close", "volume", "symbol", "source"]
    missing = set(required).difference(frame.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    cleaned = frame.copy()
    cleaned["price_date"] = pd.to_datetime(cleaned["price_date"]).dt.date
    for column in ["open", "high", "low", "close", "adjusted_close"]:
        cleaned[column] = pd.to_numeric(cleaned[column], errors="coerce")
    cleaned["volume"] = pd.to_numeric(cleaned["volume"], errors="coerce").fillna(0).astype(int)
    cleaned = cleaned.dropna(subset=["open", "high", "low", "close"])
    cleaned = cleaned[cleaned["volume"] >= 0]
    cleaned = cleaned.drop_duplicates(subset=["symbol", "price_date", "source"])
    return cleaned.sort_values(["symbol", "price_date"])


def _decimal(value: object) -> Decimal | None:
    if value is None or pd.isna(value):
        return None
    return Decimal(str(value))


def _upsert_ticker(db: Session, symbol: str) -> Ticker:
    stmt = insert(Ticker).values(symbol=symbol, name=symbol, asset_type="equity")
    stmt = stmt.on_conflict_do_update(
        index_elements=[Ticker.symbol],
        set_={"updated_at": datetime.now(UTC), "is_active": True},
    ).returning(Ticker.id)
    ticker_id = db.execute(stmt).scalar_one()
    return db.get(Ticker, ticker_id)


def _upsert_prices(db: Session, ticker: Ticker, prices: pd.DataFrame) -> int:
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
        return 0

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
            "updated_at": datetime.now(UTC),
        },
    )
    db.execute(stmt)
    return len(rows)


def _upsert_metrics(db: Session, ticker: Ticker, prices: pd.DataFrame) -> int:
    metrics = compute_metrics(prices)
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
        for row in metrics.itertuples(index=False)
    ]
    if not rows:
        return 0

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
            "updated_at": datetime.now(UTC),
        },
    )
    db.execute(stmt)
    return len(rows)


async def run_market_data_etl(
    db: Session,
    settings: Settings,
    symbols: list[str] | None,
    start_date: date | None,
    end_date: date | None,
) -> EtlJob:
    normalized_symbols = [s.upper() for s in (symbols or settings.default_symbol_list)]
    job = EtlJob(
        job_type="market_data",
        status=EtlStatus.RUNNING.value,
        symbols=normalized_symbols,
        started_at=datetime.now(UTC),
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    provider = get_market_data_provider(settings.market_data_provider)
    rows_extracted = 0
    rows_loaded = 0

    try:
        for symbol in normalized_symbols:
            logger.info("Running ETL for %s", symbol)
            raw_prices = await provider.fetch_history(symbol, start_date, end_date)
            prices = _clean_prices(raw_prices)
            rows_extracted += len(prices)
            ticker = _upsert_ticker(db, symbol)
            rows_loaded += _upsert_prices(db, ticker, prices)
            _upsert_metrics(db, ticker, prices)

        job.status = EtlStatus.SUCCEEDED.value
        job.rows_extracted = rows_extracted
        job.rows_loaded = rows_loaded
        job.finished_at = datetime.now(UTC)
        db.commit()
        db.refresh(job)
        return job
    except Exception as exc:
        db.rollback()
        persisted_job = db.execute(select(EtlJob).where(EtlJob.id == job.id)).scalar_one()
        persisted_job.status = EtlStatus.FAILED.value
        persisted_job.error_message = str(exc)
        persisted_job.rows_extracted = rows_extracted
        persisted_job.rows_loaded = rows_loaded
        persisted_job.finished_at = datetime.now(UTC)
        db.commit()
        logger.exception("ETL job %s failed", job.id)
        return persisted_job

