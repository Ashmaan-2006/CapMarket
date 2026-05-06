from datetime import date

import pandas as pd
import pytest

from app.services.transforms import PriceTransformError, clean_price_history


def test_clean_price_history_normalizes_and_deduplicates_rows() -> None:
    raw = pd.DataFrame(
        [
            {
                "price_date": "2024-01-02",
                "open": "100.1",
                "high": "101.2",
                "low": "99.5",
                "close": "100.9",
                "volume": "1000000",
                "symbol": " aapl ",
                "source": "STOOQ",
            },
            {
                "price_date": "2024-01-02",
                "open": "100.2",
                "high": "101.5",
                "low": "99.7",
                "close": "101.1",
                "volume": "1000100",
                "symbol": "AAPL",
                "source": "stooq",
            },
        ]
    )

    cleaned = clean_price_history(raw)

    assert len(cleaned) == 1
    assert cleaned.iloc[0]["symbol"] == "AAPL"
    assert cleaned.iloc[0]["source"] == "stooq"
    assert cleaned.iloc[0]["price_date"] == date(2024, 1, 2)
    assert cleaned.iloc[0]["close"] == 101.1
    assert cleaned.iloc[0]["adjusted_close"] == 101.1


def test_clean_price_history_filters_invalid_market_rows() -> None:
    raw = pd.DataFrame(
        [
            {
                "price_date": "2024-01-02",
                "open": 10,
                "high": 9,
                "low": 11,
                "close": 10,
                "volume": 100,
                "symbol": "MSFT",
                "source": "fixture",
            },
            {
                "price_date": "bad-date",
                "open": 10,
                "high": 12,
                "low": 9,
                "close": 11,
                "volume": 100,
                "symbol": "MSFT",
                "source": "fixture",
            },
        ]
    )

    cleaned = clean_price_history(raw)

    assert cleaned.empty


def test_clean_price_history_requires_core_columns() -> None:
    with pytest.raises(PriceTransformError):
        clean_price_history(pd.DataFrame({"symbol": ["AAPL"]}))
