from datetime import date
from decimal import Decimal

from app.core.config import Settings
from app.services.reports import (
    LocalFallbackReportProvider,
    OpenAiReportProvider,
    ReportMetricSnapshot,
    _build_signals,
    build_metrics_snapshot,
    get_report_provider,
)


def test_report_metric_snapshot_serializes_for_prompt() -> None:
    snapshot = ReportMetricSnapshot(
        symbol="AAPL",
        report_date=date(2024, 1, 2),
        latest_price=190.5,
        volume=10_000_000,
        daily_return=0.04,
        weekly_return=0.08,
        monthly_return=0.12,
        volatility_20d=0.025,
        sma_20=180.0,
        sma_50=170.0,
        ema_20=181.0,
        drawdown=-0.02,
        volume_ratio_20d=2.4,
        signals=["large_positive_daily_return"],
    )

    payload = snapshot.to_prompt_payload()

    assert payload["symbol"] == "AAPL"
    assert payload["report_date"] == "2024-01-02"
    assert payload["latest_price"] == 190.5


def test_build_signals_flags_metric_anomalies() -> None:
    snapshot = ReportMetricSnapshot(
        symbol="TSLA",
        report_date=date(2024, 1, 2),
        latest_price=210.0,
        volume=20_000_000,
        daily_return=0.052,
        weekly_return=0.02,
        monthly_return=-0.01,
        volatility_20d=0.04,
        sma_20=200.0,
        sma_50=220.0,
        ema_20=205.0,
        drawdown=-0.12,
        volume_ratio_20d=2.2,
    )

    signals = _build_signals(snapshot)

    assert "large_positive_daily_return" in signals
    assert "unusually_high_volume" in signals
    assert "material_drawdown" in signals
    assert "price_above_20d_sma" in signals


def test_local_fallback_provider_uses_snapshot_signals() -> None:
    snapshot = ReportMetricSnapshot(
        symbol="AAPL",
        report_date=date(2024, 1, 2),
        latest_price=190.5,
        volume=10_000_000,
        daily_return=0.04,
        weekly_return=0.08,
        monthly_return=0.12,
        volatility_20d=0.025,
        sma_20=180.0,
        sma_50=170.0,
        ema_20=181.0,
        drawdown=-0.02,
        volume_ratio_20d=2.4,
        signals=["large_positive_daily_return"],
    )

    result = LocalFallbackReportProvider().generate(snapshot)

    assert result.model == "local-fallback"
    assert "AAPL" in result.output.summary
    assert result.output.anomaly_explanations == ["Detected signal: large positive daily return"]


def test_get_report_provider_selects_configured_provider() -> None:
    fallback = get_report_provider(Settings(openai_api_key=None))
    configured = get_report_provider(Settings(openai_api_key="test-key"))

    assert isinstance(fallback, LocalFallbackReportProvider)
    assert isinstance(configured, OpenAiReportProvider)


def test_build_metrics_snapshot_limits_latest_metric_and_price_queries() -> None:
    executed_statements = []

    class FakeResult:
        def __init__(self, value) -> None:
            self.value = value

        def scalar_one_or_none(self):
            return self.value

    class FakeSession:
        def execute(self, statement):
            executed_statements.append(statement)
            if len(executed_statements) == 1:
                return FakeResult(type("TickerRecord", (), {"id": 1, "symbol": "AAPL"})())
            if len(executed_statements) == 2:
                return FakeResult(
                    type(
                        "MetricRecord",
                        (),
                        {
                            "metric_date": date(2024, 1, 2),
                            "daily_return": Decimal("0.05"),
                            "weekly_return": Decimal("0.04"),
                            "monthly_return": None,
                            "volatility_20d": Decimal("0.01"),
                            "sma_20": Decimal("100"),
                            "sma_50": Decimal("95"),
                            "ema_20": Decimal("99"),
                            "drawdown": Decimal("-0.02"),
                            "volume_ratio_20d": Decimal("2.2"),
                        },
                    )()
                )
            return FakeResult(type("PriceRecord", (), {"close": Decimal("105"), "volume": 1000})())

    snapshot = build_metrics_snapshot(FakeSession(), "AAPL", None)

    assert snapshot.symbol == "AAPL"
    assert snapshot.latest_price == 105.0
    assert executed_statements[1]._limit_clause.value == 1
    assert executed_statements[2]._limit_clause.value == 1
