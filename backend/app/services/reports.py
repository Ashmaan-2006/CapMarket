from datetime import date
from typing import Any

from openai import OpenAI
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models import AiReport, ComputedMetric, HistoricalPrice, Ticker


class AnalystReportOutput(BaseModel):
    summary: str
    trend_insights: list[str]
    anomaly_explanations: list[str]
    risk_notes: list[str]


def build_metrics_snapshot(db: Session, symbol: str, report_date: date | None) -> dict[str, Any]:
    ticker = db.execute(select(Ticker).where(Ticker.symbol == symbol.upper())).scalar_one_or_none()
    if ticker is None:
        raise ValueError(f"Ticker {symbol.upper()} not found")

    metric_query = select(ComputedMetric).where(ComputedMetric.ticker_id == ticker.id)
    if report_date:
        metric_query = metric_query.where(ComputedMetric.metric_date <= report_date)
    metric = db.execute(metric_query.order_by(desc(ComputedMetric.metric_date))).scalar_one_or_none()
    if metric is None:
        raise ValueError(f"No computed metrics found for {ticker.symbol}")

    price = db.execute(
        select(HistoricalPrice)
        .where(HistoricalPrice.ticker_id == ticker.id, HistoricalPrice.price_date <= metric.metric_date)
        .order_by(desc(HistoricalPrice.price_date))
    ).scalar_one_or_none()

    return {
        "symbol": ticker.symbol,
        "report_date": metric.metric_date.isoformat(),
        "latest_price": float(price.close) if price else None,
        "volume": price.volume if price else None,
        "daily_return": float(metric.daily_return) if metric.daily_return is not None else None,
        "weekly_return": float(metric.weekly_return) if metric.weekly_return is not None else None,
        "monthly_return": float(metric.monthly_return) if metric.monthly_return is not None else None,
        "volatility_20d": float(metric.volatility_20d) if metric.volatility_20d is not None else None,
        "sma_20": float(metric.sma_20) if metric.sma_20 is not None else None,
        "sma_50": float(metric.sma_50) if metric.sma_50 is not None else None,
        "ema_20": float(metric.ema_20) if metric.ema_20 is not None else None,
        "drawdown": float(metric.drawdown) if metric.drawdown is not None else None,
        "volume_ratio_20d": float(metric.volume_ratio_20d) if metric.volume_ratio_20d is not None else None,
    }


def generate_report(db: Session, settings: Settings, symbol: str, report_date: date | None, report_type: str) -> AiReport:
    snapshot = build_metrics_snapshot(db, symbol, report_date)
    ticker = db.execute(select(Ticker).where(Ticker.symbol == symbol.upper())).scalar_one()

    if not settings.openai_api_key:
        output = AnalystReportOutput(
            summary=f"{ticker.symbol} report generated from stored metrics for {snapshot['report_date']}.",
            trend_insights=["AI provider is not configured; metrics snapshot is available for review."],
            anomaly_explanations=[],
            risk_notes=["Set OPENAI_API_KEY to enable analyst-style report generation."],
        )
        model = "local-fallback"
    else:
        client = OpenAI(api_key=settings.openai_api_key)
        completion = client.beta.chat.completions.parse(
            model=settings.openai_model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a capital markets analyst. Generate concise reporting from the "
                        "provided structured metrics only. Do not invent news, catalysts, prices, "
                        "or facts outside the input. Explain anomalies using metric evidence."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Structured metrics snapshot: {snapshot}",
                },
            ],
            response_format=AnalystReportOutput,
        )
        output = completion.choices[0].message.parsed
        if output is None:
            raise ValueError("AI provider returned an empty report")
        model = settings.openai_model

    report = AiReport(
        ticker_id=ticker.id,
        report_date=date.fromisoformat(snapshot["report_date"]),
        report_type=report_type,
        summary=output.summary,
        trend_insights=output.trend_insights,
        anomaly_explanations=output.anomaly_explanations,
        risk_notes=output.risk_notes,
        metrics_snapshot=snapshot,
        model=model,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report

