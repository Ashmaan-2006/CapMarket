from datetime import date
from decimal import Decimal

import pandas as pd
import pytest

from app.repositories.market_data import _decimal, list_top_movers, upsert_computed_metrics


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


def test_upsert_computed_metrics_validates_required_columns() -> None:
    with pytest.raises(ValueError):
        upsert_computed_metrics(db=None, ticker=None, metrics=pd.DataFrame({"metric_date": [date(2024, 1, 2)]}))


def test_top_movers_latest_date_query_is_limited(monkeypatch) -> None:
    executed_statements = []

    class FakeResult:
        def __init__(self, scalar_value=None, rows=None) -> None:
            self.scalar_value = scalar_value
            self.rows = rows or []

        def scalar_one_or_none(self):
            return self.scalar_value

        def all(self):
            return self.rows

    class FakeSession:
        def execute(self, statement):
            executed_statements.append(statement)
            if len(executed_statements) == 1:
                return FakeResult(scalar_value=date(2024, 1, 2))
            return FakeResult(
                rows=[
                    (
                        "AAPL",
                        date(2024, 1, 2),
                        Decimal("0.05"),
                        Decimal("1.4"),
                    )
                ]
            )

    result = list_top_movers(FakeSession(), limit=5)

    assert result.metric_date == date(2024, 1, 2)
    assert result.items[0].symbol == "AAPL"
    assert executed_statements[0]._limit_clause.value == 1
