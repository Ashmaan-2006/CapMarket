from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select, text
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db import get_db
from app.errors import not_found, service_unavailable, validation_failed
from app.models import AiReport, ComputedMetric, EtlJob, HistoricalPrice, Ticker
from app.repositories.market_data import list_tickers as list_ticker_records
from app.schemas import (
    AiReportRead,
    MarketDataRead,
    EtlJobRead,
    EtlRunRequest,
    EtlStatusRead,
    EtlStatusName,
    HealthRead,
    MetricRead,
    MetricsRead,
    PriceRead,
    ReportGenerateRequest,
    TickerRead,
    TickerListRead,
    TopMoverRead,
    normalize_symbol,
)
from app.services.etl import list_etl_jobs, run_market_data_etl
from app.services.reports import generate_report

router = APIRouter()


def _normalize_symbol_param(value: str) -> str:
    try:
        return normalize_symbol(value)
    except ValueError as exc:
        raise validation_failed(str(exc)) from exc


@router.get("/health", response_model=HealthRead)
def health(settings: Settings = Depends(get_settings)) -> HealthRead:
    return HealthRead(status="ok", environment=settings.app_env)


@router.get("/health/ready", response_model=HealthRead)
def readiness(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> HealthRead:
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:
        raise service_unavailable("Database is not ready") from exc
    return HealthRead(status="ready", environment=settings.app_env)


@router.get("/tickers", response_model=TickerListRead)
def list_tickers(
    db: Session = Depends(get_db),
    search: str | None = None,
    active_only: bool = True,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> TickerListRead:
    normalized_search = _normalize_symbol_param(search) if search else None
    result = list_ticker_records(
        db,
        search=normalized_search,
        active_only=active_only,
        limit=limit,
        offset=offset,
    )
    return TickerListRead(
        items=[TickerRead.model_validate(item) for item in result.items],
        limit=limit,
        offset=offset,
        count=len(result.items),
        total=result.total,
        search=normalized_search,
        active_only=active_only,
    )


@router.get("/market-data/{symbol}", response_model=MarketDataRead)
def get_market_data(
    symbol: str,
    db: Session = Depends(get_db),
    start_date: date | None = None,
    end_date: date | None = None,
    limit: int = Query(default=252, ge=1, le=1500),
    offset: int = Query(default=0, ge=0),
) -> MarketDataRead:
    normalized_symbol = _normalize_symbol_param(symbol)
    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=422, detail="start_date must be before or equal to end_date")

    ticker = db.execute(select(Ticker).where(Ticker.symbol == normalized_symbol)).scalar_one_or_none()
    if ticker is None:
        raise not_found("Ticker", normalized_symbol)

    query = select(HistoricalPrice).where(HistoricalPrice.ticker_id == ticker.id)
    if start_date:
        query = query.where(HistoricalPrice.price_date >= start_date)
    if end_date:
        query = query.where(HistoricalPrice.price_date <= end_date)
    query = query.order_by(HistoricalPrice.price_date).limit(limit).offset(offset)
    items = list(db.execute(query).scalars())
    return MarketDataRead(
        symbol=normalized_symbol,
        start_date=start_date,
        end_date=end_date,
        items=[PriceRead.model_validate(item) for item in items],
        limit=limit,
        offset=offset,
        count=len(items),
    )


@router.get("/metrics/{symbol}", response_model=MetricsRead)
def get_metrics(
    symbol: str,
    db: Session = Depends(get_db),
    limit: int = Query(default=252, ge=1, le=1500),
    offset: int = Query(default=0, ge=0),
) -> MetricsRead:
    normalized_symbol = _normalize_symbol_param(symbol)
    ticker = db.execute(select(Ticker).where(Ticker.symbol == normalized_symbol)).scalar_one_or_none()
    if ticker is None:
        raise not_found("Ticker", normalized_symbol)

    query = (
        select(ComputedMetric)
        .where(ComputedMetric.ticker_id == ticker.id)
        .order_by(ComputedMetric.metric_date)
        .limit(limit)
        .offset(offset)
    )
    items = list(db.execute(query).scalars())
    return MetricsRead(
        symbol=normalized_symbol,
        items=[MetricRead.model_validate(item) for item in items],
        limit=limit,
        offset=offset,
        count=len(items),
    )


@router.get("/top-movers", response_model=list[TopMoverRead])
def get_top_movers(
    db: Session = Depends(get_db),
    metric_date: date | None = None,
    direction: str = Query(default="gainers", pattern="^(gainers|losers)$"),
    limit: int = Query(default=10, ge=1, le=50),
) -> list[TopMoverRead]:
    if metric_date is None:
        metric_date = db.execute(select(ComputedMetric.metric_date).order_by(desc(ComputedMetric.metric_date))).scalar_one_or_none()
    if metric_date is None:
        return []

    order_column = desc(ComputedMetric.daily_return) if direction == "gainers" else ComputedMetric.daily_return
    rows = db.execute(
        select(Ticker.symbol, ComputedMetric.metric_date, ComputedMetric.daily_return, ComputedMetric.volume_ratio_20d)
        .join(ComputedMetric, ComputedMetric.ticker_id == Ticker.id)
        .where(ComputedMetric.metric_date == metric_date)
        .order_by(order_column)
        .limit(limit)
    ).all()
    return [TopMoverRead(symbol=row[0], metric_date=row[1], daily_return=row[2], volume_ratio_20d=row[3]) for row in rows]


@router.post("/etl/run", response_model=EtlJobRead, status_code=202)
async def run_etl(
    payload: EtlRunRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> EtlJob:
    return await run_market_data_etl(db, settings, payload.symbols, payload.start_date, payload.end_date)


@router.get("/etl/status", response_model=EtlStatusRead)
def get_etl_status(
    db: Session = Depends(get_db),
    status: EtlStatusName | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> EtlStatusRead:
    items = list_etl_jobs(db, status=status, limit=limit, offset=offset)
    return EtlStatusRead(
        items=[EtlJobRead.model_validate(item) for item in items],
        limit=limit,
        offset=offset,
        count=len(items),
        status=status,
    )


@router.get("/reports/{symbol}", response_model=list[AiReportRead])
def get_reports(symbol: str, db: Session = Depends(get_db), limit: int = Query(default=10, ge=1, le=50)) -> list[AiReportRead]:
    normalized_symbol = _normalize_symbol_param(symbol)
    ticker = db.execute(select(Ticker).where(Ticker.symbol == normalized_symbol)).scalar_one_or_none()
    if ticker is None:
        raise not_found("Ticker", normalized_symbol)

    reports = db.execute(
        select(AiReport).where(AiReport.ticker_id == ticker.id).order_by(desc(AiReport.created_at)).limit(limit)
    ).scalars()
    return [
        AiReportRead(
            id=report.id,
            symbol=ticker.symbol,
            report_date=report.report_date,
            report_type=report.report_type,
            summary=report.summary,
            trend_insights=report.trend_insights,
            anomaly_explanations=report.anomaly_explanations,
            risk_notes=report.risk_notes,
            metrics_snapshot=report.metrics_snapshot,
            model=report.model,
            created_at=report.created_at,
        )
        for report in reports
    ]


@router.post("/reports/generate", response_model=AiReportRead)
def create_report(
    payload: ReportGenerateRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AiReportRead:
    try:
        report = generate_report(db, settings, payload.symbol, payload.report_date, payload.report_type)
    except ValueError as exc:
        raise not_found("Report input", str(exc)) from exc

    ticker = db.get(Ticker, report.ticker_id)
    return AiReportRead(
        id=report.id,
        symbol=ticker.symbol,
        report_date=report.report_date,
        report_type=report.report_type,
        summary=report.summary,
        trend_insights=report.trend_insights,
        anomaly_explanations=report.anomaly_explanations,
        risk_notes=report.risk_notes,
        metrics_snapshot=report.metrics_snapshot,
        model=report.model,
        created_at=report.created_at,
    )
