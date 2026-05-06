from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app import api
from app.db import get_db
from app.main import create_app
from app.repositories.market_data import (
    MetricHistoryResult,
    PriceHistoryResult,
    TickerListResult,
    TopMoverRecord,
    TopMoversResult,
)
from app.repositories.reports import ReportListResult


def _client(db: object | None = None) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db or object()
    return TestClient(app)


def test_health_endpoint_returns_environment() -> None:
    client = _client()

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["service"] == "capital-markets-api"


def test_request_context_headers_are_returned() -> None:
    client = _client()

    response = client.get("/health", headers={"X-Request-ID": "test-request-123"})

    assert response.headers["X-Request-ID"] == "test-request-123"
    assert float(response.headers["X-Process-Time-ms"]) >= 0


def test_tickers_endpoint_returns_paginated_payload(monkeypatch) -> None:
    ticker = SimpleNamespace(
        id=1,
        symbol="AAPL",
        name="AAPL",
        asset_type="equity",
        exchange=None,
        currency="USD",
        is_active=True,
    )

    def fake_list_tickers(db, *, search, active_only, limit, offset):
        assert search == "AAP"
        assert active_only is True
        assert limit == 25
        assert offset == 0
        return TickerListResult(items=[ticker], total=1)

    monkeypatch.setattr(api, "list_ticker_records", fake_list_tickers)
    client = _client()

    response = client.get("/tickers?search=aap&limit=25")

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["total"] == 1
    assert body["items"][0]["symbol"] == "AAPL"


def test_market_data_endpoint_validates_date_range() -> None:
    client = _client()

    response = client.get("/market-data/AAPL?start_date=2024-02-01&end_date=2024-01-01")

    assert response.status_code == 422


def test_market_data_endpoint_returns_404_for_missing_ticker(monkeypatch) -> None:
    monkeypatch.setattr(
        api,
        "list_historical_prices",
        lambda *args, **kwargs: PriceHistoryResult(ticker=None, items=[], total=0),
    )
    client = _client()

    response = client.get("/market-data/NOPE")

    assert response.status_code == 404


def test_metrics_endpoint_returns_history_payload(monkeypatch) -> None:
    ticker = SimpleNamespace(symbol="AAPL")
    metric = SimpleNamespace(
        metric_date=date(2024, 1, 2),
        daily_return=Decimal("0.01"),
        weekly_return=None,
        monthly_return=None,
        volatility_20d=None,
        sma_20=None,
        sma_50=None,
        ema_20=None,
        drawdown=None,
        volume_ratio_20d=None,
    )
    monkeypatch.setattr(
        api,
        "list_computed_metrics",
        lambda *args, **kwargs: MetricHistoryResult(ticker=ticker, items=[metric], total=1),
    )
    client = _client()

    response = client.get("/metrics/aapl")

    assert response.status_code == 200
    body = response.json()
    assert body["symbol"] == "AAPL"
    assert body["total"] == 1
    assert body["items"][0]["daily_return"] == "0.01"


def test_top_movers_endpoint_returns_envelope(monkeypatch) -> None:
    monkeypatch.setattr(
        api,
        "list_top_movers",
        lambda *args, **kwargs: TopMoversResult(
            items=[
                TopMoverRecord(
                    symbol="MSFT",
                    metric_date=date(2024, 1, 2),
                    daily_return=Decimal("0.05"),
                    volume_ratio_20d=Decimal("1.4"),
                )
            ],
            metric_date=date(2024, 1, 2),
            direction="gainers",
        ),
    )
    client = _client()

    response = client.get("/top-movers")

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["items"][0]["symbol"] == "MSFT"


def test_etl_status_endpoint_filters_jobs(monkeypatch) -> None:
    job = SimpleNamespace(
        id=1,
        job_type="market_data",
        status="succeeded",
        symbols=["AAPL"],
        started_at=datetime(2024, 1, 1, tzinfo=UTC),
        finished_at=datetime(2024, 1, 1, 0, 1, tzinfo=UTC),
        rows_extracted=10,
        rows_loaded=10,
        error_message=None,
        metadata_json={"provider": "fixture"},
    )

    def fake_list_jobs(db, *, status, limit, offset):
        assert status == "succeeded"
        assert limit == 5
        assert offset == 0
        return [job]

    monkeypatch.setattr(api, "list_etl_jobs", fake_list_jobs)
    client = _client()

    response = client.get("/etl/status?status=succeeded&limit=5")

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["items"][0]["status"] == "succeeded"


def test_reports_endpoint_returns_paginated_payload(monkeypatch) -> None:
    ticker = SimpleNamespace(id=1, symbol="AAPL")
    report = SimpleNamespace(
        id=10,
        ticker_id=1,
        report_date=date(2024, 1, 2),
        report_type="daily",
        summary="AAPL advanced on elevated volume.",
        trend_insights=["Price remains above the 20 day average."],
        anomaly_explanations=["Volume ratio is above the anomaly threshold."],
        risk_notes=["Momentum could reverse if volume normalizes."],
        metrics_snapshot={"daily_return": 0.02},
        model="local-fallback",
        created_at=datetime(2024, 1, 2, tzinfo=UTC),
    )

    def fake_list_reports(db, *, symbol, limit, offset):
        assert symbol == "AAPL"
        assert limit == 5
        assert offset == 0
        return ReportListResult(ticker=ticker, items=[report], total=1)

    monkeypatch.setattr(api, "list_ai_reports", fake_list_reports)
    client = _client()

    response = client.get("/reports/aapl?limit=5")

    assert response.status_code == 200
    body = response.json()
    assert body["symbol"] == "AAPL"
    assert body["count"] == 1
    assert body["total"] == 1
    assert body["items"][0]["summary"] == "AAPL advanced on elevated volume."
    assert body["items"][0]["metrics_snapshot"] == {"daily_return": 0.02}


def test_reports_endpoint_returns_404_for_missing_ticker(monkeypatch) -> None:
    monkeypatch.setattr(
        api,
        "list_ai_reports",
        lambda *args, **kwargs: ReportListResult(ticker=None, items=[], total=0),
    )
    client = _client()

    response = client.get("/reports/NOPE")

    assert response.status_code == 404


def test_generate_report_endpoint_persists_and_returns_report(monkeypatch) -> None:
    ticker = SimpleNamespace(id=1, symbol="MSFT")
    db = SimpleNamespace(get=lambda model, ticker_id: ticker)
    report = SimpleNamespace(
        id=20,
        ticker_id=1,
        report_date=date(2024, 1, 3),
        report_type="daily",
        summary="MSFT report generated from stored metrics.",
        trend_insights=["Weekly return remains positive."],
        anomaly_explanations=[],
        risk_notes=["No material risk flags in the stored snapshot."],
        metrics_snapshot={"weekly_return": 0.04},
        model="local-fallback",
        created_at=datetime(2024, 1, 3, tzinfo=UTC),
    )

    def fake_generate_report(db_arg, settings, symbol, report_date, report_type):
        assert db_arg is db
        assert symbol == "MSFT"
        assert report_date == date(2024, 1, 3)
        assert report_type == "daily"
        return report

    monkeypatch.setattr(api, "generate_report", fake_generate_report)
    client = _client(db=db)

    response = client.post(
        "/reports/generate",
        json={"symbol": "msft", "report_date": "2024-01-03", "report_type": "daily"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["symbol"] == "MSFT"
    assert body["summary"] == "MSFT report generated from stored metrics."
    assert body["metrics_snapshot"] == {"weekly_return": 0.04}
