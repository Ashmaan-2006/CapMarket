from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

import pandas as pd
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import HistoricalPrice, Ticker


@dataclass(frozen=True)
class PriceLoadResult:
    ticker: Ticker
    rows_submitted: int


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
