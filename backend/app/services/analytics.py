from decimal import Decimal

import numpy as np
import pandas as pd


def _to_decimal(value: float | int | None) -> Decimal | None:
    if value is None or pd.isna(value) or np.isinf(value):
        return None
    return Decimal(str(round(float(value), 8)))


def compute_metrics(prices: pd.DataFrame) -> pd.DataFrame:
    required = {"price_date", "close", "volume"}
    missing = required.difference(prices.columns)
    if missing:
        raise ValueError(f"Missing required price columns: {sorted(missing)}")

    frame = prices.copy()
    frame["price_date"] = pd.to_datetime(frame["price_date"])
    frame = frame.sort_values("price_date")
    frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
    frame["volume"] = pd.to_numeric(frame["volume"], errors="coerce")
    frame = frame.dropna(subset=["close", "volume"])

    frame["daily_return"] = frame["close"].pct_change()
    frame["weekly_return"] = frame["close"].pct_change(periods=5)
    frame["monthly_return"] = frame["close"].pct_change(periods=21)
    frame["volatility_20d"] = frame["daily_return"].rolling(window=20).std()
    frame["sma_20"] = frame["close"].rolling(window=20).mean()
    frame["sma_50"] = frame["close"].rolling(window=50).mean()
    frame["ema_20"] = frame["close"].ewm(span=20, adjust=False).mean()
    frame["running_high"] = frame["close"].cummax()
    frame["drawdown"] = frame["close"] / frame["running_high"] - 1
    frame["volume_ratio_20d"] = frame["volume"] / frame["volume"].rolling(window=20).mean()

    metrics = frame[
        [
            "price_date",
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
    ].rename(columns={"price_date": "metric_date"})

    for column in metrics.columns:
        if column != "metric_date":
            metrics[column] = metrics[column].map(_to_decimal)

    metrics["metric_date"] = metrics["metric_date"].dt.date
    return metrics

