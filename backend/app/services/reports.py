from datetime import date
from decimal import Decimal
from typing import Any, Protocol

from openai import OpenAI
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models import AiReport, ComputedMetric, HistoricalPrice, Ticker


class AnalystReportOutput(BaseModel):
    summary: str
    trend_insights: list[str]
    anomaly_explanations: list[str]
    risk_notes: list[str]


class ReportProviderResult(BaseModel):
    output: AnalystReportOutput
    model: str


class ReportProvider(Protocol):
    def generate(self, snapshot: "ReportMetricSnapshot") -> ReportProviderResult:
        pass


class ReportMetricSnapshot(BaseModel):
    symbol: str
    report_date: date
    latest_price: float | None
    volume: int | None
    daily_return: float | None
    weekly_return: float | None
    monthly_return: float | None
    volatility_20d: float | None
    sma_20: float | None
    sma_50: float | None
    ema_20: float | None
    drawdown: float | None
    volume_ratio_20d: float | None
    signals: list[str] = Field(default_factory=list)

    def to_prompt_payload(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


REPORT_SYSTEM_PROMPT = (
    "You are a capital markets analyst. Generate concise reporting from the provided "
    "structured metrics only. Do not invent news, catalysts, prices, or facts outside "
    "the input. Explain anomalies using metric evidence."
)


class LocalFallbackReportProvider:
    model = "local-fallback"

    def generate(self, snapshot: ReportMetricSnapshot) -> ReportProviderResult:
        output = AnalystReportOutput(
            summary=(
                f"{snapshot.symbol} report generated from stored metrics for "
                f"{snapshot.report_date.isoformat()}."
            ),
            trend_insights=["AI provider is not configured; metrics snapshot is available for review."],
            anomaly_explanations=[
                f"Detected signal: {signal.replace('_', ' ')}" for signal in snapshot.signals
            ],
            risk_notes=["Set OPENAI_API_KEY to enable analyst-style report generation."],
        )
        return ReportProviderResult(output=output, model=self.model)


class OpenAiReportProvider:
    def __init__(self, api_key: str, model: str) -> None:
        self.client = OpenAI(api_key=api_key)
        self.model = model

    def generate(self, snapshot: ReportMetricSnapshot) -> ReportProviderResult:
        completion = self.client.beta.chat.completions.parse(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": REPORT_SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": f"Structured metrics snapshot: {snapshot.to_prompt_payload()}",
                },
            ],
            response_format=AnalystReportOutput,
        )
        output = completion.choices[0].message.parsed
        if output is None:
            raise ValueError("AI provider returned an empty report")
        return ReportProviderResult(output=output, model=self.model)


def get_report_provider(settings: Settings) -> ReportProvider:
    if settings.openai_api_key:
        return OpenAiReportProvider(api_key=settings.openai_api_key, model=settings.openai_model)
    return LocalFallbackReportProvider()


def _decimal_to_float(value: Decimal | None) -> float | None:
    return float(value) if value is not None else None


def _build_signals(snapshot: ReportMetricSnapshot) -> list[str]:
    signals: list[str] = []
    if snapshot.daily_return is not None and abs(snapshot.daily_return) >= 0.03:
        direction = "positive" if snapshot.daily_return > 0 else "negative"
        signals.append(f"large_{direction}_daily_return")
    if snapshot.volume_ratio_20d is not None and snapshot.volume_ratio_20d >= 2:
        signals.append("unusually_high_volume")
    if snapshot.drawdown is not None and snapshot.drawdown <= -0.10:
        signals.append("material_drawdown")
    if (
        snapshot.latest_price is not None
        and snapshot.sma_20 is not None
        and snapshot.latest_price > snapshot.sma_20
    ):
        signals.append("price_above_20d_sma")
    return signals


def build_metrics_snapshot(db: Session, symbol: str, report_date: date | None) -> ReportMetricSnapshot:
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

    snapshot = ReportMetricSnapshot(
        symbol=ticker.symbol,
        report_date=metric.metric_date,
        latest_price=float(price.close) if price else None,
        volume=price.volume if price else None,
        daily_return=_decimal_to_float(metric.daily_return),
        weekly_return=_decimal_to_float(metric.weekly_return),
        monthly_return=_decimal_to_float(metric.monthly_return),
        volatility_20d=_decimal_to_float(metric.volatility_20d),
        sma_20=_decimal_to_float(metric.sma_20),
        sma_50=_decimal_to_float(metric.sma_50),
        ema_20=_decimal_to_float(metric.ema_20),
        drawdown=_decimal_to_float(metric.drawdown),
        volume_ratio_20d=_decimal_to_float(metric.volume_ratio_20d),
    )
    return snapshot.model_copy(update={"signals": _build_signals(snapshot)})


def generate_report(db: Session, settings: Settings, symbol: str, report_date: date | None, report_type: str) -> AiReport:
    snapshot = build_metrics_snapshot(db, symbol, report_date)
    ticker = db.execute(select(Ticker).where(Ticker.symbol == symbol.upper())).scalar_one()
    prompt_payload = snapshot.to_prompt_payload()
    provider_result = get_report_provider(settings).generate(snapshot)
    output = provider_result.output

    report = AiReport(
        ticker_id=ticker.id,
        report_date=snapshot.report_date,
        report_type=report_type,
        summary=output.summary,
        trend_insights=output.trend_insights,
        anomaly_explanations=output.anomaly_explanations,
        risk_notes=output.risk_notes,
        metrics_snapshot=prompt_payload,
        model=provider_result.model,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report
