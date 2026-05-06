from datetime import date, timedelta

import pandas as pd
import pytest

from app.services.analytics import AnalyticsError, compute_analytics, compute_metrics, rank_top_movers


def _price_frame(closes: list[float], volumes: list[int] | None = None) -> pd.DataFrame:
    start = date(2024, 1, 1)
    return pd.DataFrame(
        {
            "price_date": [start + timedelta(days=i) for i in range(len(closes))],
            "close": closes,
            "volume": volumes or [1_000_000 for _ in closes],
        }
    )


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


def test_compute_metrics_calculates_return_windows() -> None:
    prices = _price_frame([100, 102, 104, 106, 108, 110, 112, 114, 116, 118])

    metrics = compute_metrics(prices)

    assert metrics.iloc[1]["daily_return"] == pytest.approx(0.02)
    assert metrics.iloc[5]["weekly_return"] == pytest.approx(0.10)


def test_compute_metrics_tracks_drawdown_and_recovery() -> None:
    prices = _price_frame([100, 120, 90, 110, 130])

    metrics = compute_metrics(prices)

    assert metrics.iloc[2]["drawdown"] == pytest.approx(-0.25)
    assert metrics.iloc[4]["drawdown"] == 0
    assert metrics.iloc[4]["max_drawdown_to_date"] == pytest.approx(-0.25)


def test_compute_metrics_calculates_volume_ratio() -> None:
    prices = _price_frame(
        closes=[100 + i for i in range(21)],
        volumes=[100 for _ in range(20)] + [200],
    )

    metrics = compute_metrics(prices)

    assert metrics.iloc[-1]["volume_ratio_20d"] == pytest.approx(200 / 105)


def test_rank_top_movers_ignores_null_returns() -> None:
    metrics = pd.DataFrame(
        {
            "metric_date": [date(2024, 1, 2), date(2024, 1, 2), date(2024, 1, 2)],
            "symbol": ["AAPL", "MSFT", "TSLA"],
            "daily_return": [None, 0.01, -0.02],
        }
    )

    ranked = rank_top_movers(metrics, limit=10)

    assert list(ranked["symbol"]) == ["MSFT", "TSLA"]
