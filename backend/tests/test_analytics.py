from datetime import date, timedelta

import pandas as pd
import pytest

from app.services.analytics import AnalyticsError, compute_analytics, compute_metrics, rank_top_movers


def test_compute_metrics_returns_expected_columns() -> None:
    start = date(2024, 1, 1)
    prices = pd.DataFrame(
        {
            "price_date": [start + timedelta(days=i) for i in range(60)],
            "close": [100 + i for i in range(60)],
            "volume": [1_000_000 + i for i in range(60)],
        }
    )

    metrics = compute_metrics(prices)

    assert len(metrics) == 60
    assert metrics.iloc[-1]["sma_20"] is not None
    assert metrics.iloc[-1]["sma_50"] is not None
    assert metrics.iloc[-1]["drawdown"] == 0
    assert metrics.iloc[-1]["annualized_volatility_20d"] is not None
    assert metrics.iloc[-1]["max_drawdown_to_date"] == 0


def test_compute_analytics_returns_latest_snapshot() -> None:
    start = date(2024, 1, 1)
    prices = pd.DataFrame(
        {
            "price_date": [start + timedelta(days=i) for i in range(60)],
            "close": [100 + i for i in range(60)],
            "volume": [1_000_000 for _ in range(60)],
        }
    )

    result = compute_analytics(prices)

    assert len(result.metrics) == 60
    assert result.latest_snapshot["metric_date"] == (start + timedelta(days=59)).isoformat()
    assert "annualized_volatility_20d" in result.latest_snapshot


def test_rank_top_movers_returns_latest_date_sorted() -> None:
    metrics = pd.DataFrame(
        {
            "metric_date": [date(2024, 1, 1), date(2024, 1, 2), date(2024, 1, 2)],
            "symbol": ["AAPL", "AAPL", "MSFT"],
            "daily_return": [0.01, 0.02, 0.05],
        }
    )

    ranked = rank_top_movers(metrics, limit=1)

    assert len(ranked) == 1
    assert ranked.iloc[0]["symbol"] == "MSFT"


def test_compute_metrics_rejects_empty_valid_price_set() -> None:
    prices = pd.DataFrame(
        {
            "price_date": ["bad-date"],
            "close": [None],
            "volume": [None],
        }
    )

    with pytest.raises(AnalyticsError):
        compute_metrics(prices)
