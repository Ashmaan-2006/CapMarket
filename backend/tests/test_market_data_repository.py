from datetime import date

import pandas as pd

from app.repositories.market_data import _decimal


def test_decimal_handles_missing_pandas_values() -> None:
    assert _decimal(None) is None
    assert _decimal(pd.NA) is None


def test_repository_price_rows_preserve_expected_columns() -> None:
    prices = pd.DataFrame(
        [
            {
                "price_date": date(2024, 1, 2),
                "open": 100,
                "high": 101,
                "low": 99,
                "close": 100.5,
                "adjusted_close": 100.5,
                "volume": 1_000_000,
                "symbol": "AAPL",
                "source": "stooq",
            }
        ]
    )

    row = next(prices.itertuples(index=False))

    assert row.price_date == date(2024, 1, 2)
    assert row.symbol == "AAPL"
    assert row.source == "stooq"
