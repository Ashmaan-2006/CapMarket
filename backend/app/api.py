from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db import get_db
from app.models import AiReport, ComputedMetric, EtlJob, HistoricalPrice, Ticker
from app.schemas import (
    AiReportRead,
    EtlJobRead,
    EtlRunRequest,
    MetricRead,
    PriceRead,
    ReportGenerateRequest,
    TickerRead,
    TopMoverRead,
)
from app.services.etl import run_market_data_etl
from app.services.reports import generate_report

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/tickers", response_model=list[TickerRead])
def list_tickers(
    db: Session = Depends(get_db),
    search: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[Ticker]:
    query = select(Ticker).order_by(Ticker.symbol).limit(limit).offset(offset)
    if search:
        query = select(Ticker).where(Ticker.symbol.ilike(f"%{search.upper()}%")).order_by(Ticker.symbol).limit(limit).offset(offset)
    return list(db.execute(query).scalars())


@router.get("/market-data/{symbol}", response_model=list[PriceRead])
def get_market_data(
    symbol: str,
    db: Session = Depends(get_db),
    start_date: date | None = None,
    end_date: date | None = None,
    limit: int = Query(default=252, ge=1, le=1500),
    offset: int = Query(default=0, ge=0),
) -> list[HistoricalPrice]:
    ticker = db.execute(select(Ticker).where(Ticker.symbol == symbol.upper())).scalar_one_or_none()
    if ticker is None:
        raise HTTPException(status_code=404, detail="Ticker not found")

    query = select(HistoricalPrice).where(HistoricalPrice.ticker_id == ticker.id)
    if start_date:
        query = query.where(HistoricalPrice.price_date >= start_date)
    if end_date:
        query = query.where(HistoricalPrice.price_date <= end_date)
    query = query.order_by(HistoricalPrice.price_date).limit(limit).offset(offset)
    return list(db.execute(query).scalars())


@router.get("/metrics/{symbol}", response_model=list[MetricRead])
def get_metrics(
    symbol: str,
    db: Session = Depends(get_db),
    limit: int = Query(default=252, ge=1, le=1500),
    offset: int = Query(default=0, ge=0),
) -> list[ComputedMetric]:
    ticker = db.execute(select(Ticker).where(Ticker.symbol == symbol.upper())).scalar_one_or_none()
    if ticker is None:
        raise HTTPException(status_code=404, detail="Ticker not found")

    query = (
        select(ComputedMetric)
        .where(ComputedMetric.ticker_id == ticker.id)
        .order_by(ComputedMetric.metric_date)
        .limit(limit)
        .offset(offset)
    )
    return list(db.execute(query).scalars())


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


@router.post("/etl/run", response_model=EtlJobRead)
async def run_etl(
    payload: EtlRunRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> EtlJob:
    return await run_market_data_etl(db, settings, payload.symbols, payload.start_date, payload.end_date)


@router.get("/etl/status", response_model=list[EtlJobRead])
def get_etl_status(
    db: Session = Depends(get_db),
    limit: int = Query(default=20, ge=1, le=100),
) -> list[EtlJob]:
    return list(db.execute(select(EtlJob).order_by(desc(EtlJob.created_at)).limit(limit)).scalars())


@router.get("/reports/{symbol}", response_model=list[AiReportRead])
def get_reports(symbol: str, db: Session = Depends(get_db), limit: int = Query(default=10, ge=1, le=50)) -> list[AiReportRead]:
    ticker = db.execute(select(Ticker).where(Ticker.symbol == symbol.upper())).scalar_one_or_none()
    if ticker is None:
        raise HTTPException(status_code=404, detail="Ticker not found")

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
        report = generate_report(db, settings, payload.symbol.upper(), payload.report_date, payload.report_type)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

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

