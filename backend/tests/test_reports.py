from datetime import date

from app.core.config import Settings
from app.services.reports import (
    LocalFallbackReportProvider,
    OpenAiReportProvider,
    ReportMetricSnapshot,
    _build_signals,
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
