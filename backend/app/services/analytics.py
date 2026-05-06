from dataclasses import dataclass
from decimal import Decimal

import numpy as np
import pandas as pd


TRADING_DAYS_PER_YEAR = 252


@dataclass(frozen=True)
class AnalyticsResult:
    metrics: pd.DataFrame
    latest_snapshot: dict[str, Decimal | None | str]


class AnalyticsError(ValueError):
    pass


def _to_decimal(value: float | int | None) -> Decimal | None:
    if value is None or pd.isna(value) or np.isinf(value):
        return None
    return Decimal(str(round(float(value), 8)))


def prepare_price_frame(prices: pd.DataFrame) -> pd.DataFrame:
    required = {"price_date", "close", "volume"}
    missing = required.difference(prices.columns)
    if missing:
        raise AnalyticsError(f"Missing required price columns: {sorted(missing)}")

    frame = prices.copy()
    frame["price_date"] = pd.to_datetime(frame["price_date"])
    frame = frame.sort_values("price_date")
    frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
    frame["volume"] = pd.to_numeric(frame["volume"], errors="coerce")
    frame = frame.dropna(subset=["close", "volume"])
    frame = frame[(frame["close"] > 0) & (frame["volume"] >= 0)]
    if frame.empty:
        raise AnalyticsError("No valid price rows available for metric computation")
    return frame


def compute_metrics(prices: pd.DataFrame) -> pd.DataFrame:
    frame = prepare_price_frame(prices)
    frame["daily_return"] = frame["close"].pct_change()
    frame["weekly_return"] = frame["close"].pct_change(periods=5)
    frame["monthly_return"] = frame["close"].pct_change(periods=21)
    frame["volatility_20d"] = frame["daily_return"].rolling(window=20).std()
    frame["annualized_volatility_20d"] = frame["volatility_20d"] * np.sqrt(TRADING_DAYS_PER_YEAR)
    frame["sma_20"] = frame["close"].rolling(window=20).mean()
    frame["sma_50"] = frame["close"].rolling(window=50).mean()
    frame["ema_20"] = frame["close"].ewm(span=20, adjust=False).mean()
    frame["running_high"] = frame["close"].cummax()
    frame["drawdown"] = frame["close"] / frame["running_high"] - 1
    frame["max_drawdown_to_date"] = frame["drawdown"].cummin()
    frame["volume_ratio_20d"] = frame["volume"] / frame["volume"].rolling(window=20).mean()

    metrics = frame[
        [
            "price_date",
            "daily_return",
            "weekly_return",
            "monthly_return",
            "volatility_20d",
            "annualized_volatility_20d",
            "sma_20",
            "sma_50",
            "ema_20",
            "drawdown",
            "max_drawdown_to_date",
            "volume_ratio_20d",
        ]
    ].rename(columns={"price_date": "metric_date"})

    for column in metrics.columns:
        if column != "metric_date":
            metrics[column] = metrics[column].map(_to_decimal)

    metrics["metric_date"] = metrics["metric_date"].dt.date
    return metrics


def compute_analytics(prices: pd.DataFrame) -> AnalyticsResult:
    metrics = compute_metrics(prices)
    latest = metrics.iloc[-1]
    latest_snapshot = {
        "metric_date": latest["metric_date"].isoformat(),
        "daily_return": latest["daily_return"],
        "weekly_return": latest["weekly_return"],
        "monthly_return": latest["monthly_return"],
        "volatility_20d": latest["volatility_20d"],
        "annualized_volatility_20d": latest["annualized_volatility_20d"],
        "drawdown": latest["drawdown"],
        "max_drawdown_to_date": latest["max_drawdown_to_date"],
        "volume_ratio_20d": latest["volume_ratio_20d"],
    }
    return AnalyticsResult(metrics=metrics, latest_snapshot=latest_snapshot)


def rank_top_movers(metrics: pd.DataFrame, limit: int = 10) -> pd.DataFrame:
    required = {"metric_date", "daily_return"}
    missing = required.difference(metrics.columns)
    if missing:
        raise AnalyticsError(f"Missing required metric columns: {sorted(missing)}")

    ranked = metrics.dropna(subset=["daily_return"]).copy()
    if ranked.empty:
        return ranked
    latest_date = ranked["metric_date"].max()
    return ranked[ranked["metric_date"] == latest_date].sort_values(
        "daily_return",
        ascending=False,
    ).head(limit)
