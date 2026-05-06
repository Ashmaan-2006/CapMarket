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


def _client() -> TestClient:
    app = create_app()
    app.dependency_overrides[get_db] = lambda: object()
    return TestClient(app)


def test_health_endpoint_returns_environment() -> None:
    client = _client()

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["service"] == "capital-markets-api"


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
