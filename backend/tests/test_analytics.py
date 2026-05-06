from datetime import date, timedelta

import pandas as pd

from app.services.analytics import compute_metrics


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

