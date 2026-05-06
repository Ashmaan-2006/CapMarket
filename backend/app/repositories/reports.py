from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.models import AiReport, Ticker
from app.repositories.market_data import get_ticker_by_symbol


@dataclass(frozen=True)
class ReportListResult:
    ticker: Ticker | None
    items: list[AiReport]
    total: int


def list_ai_reports(
    db: Session,
    *,
    symbol: str,
    limit: int = 10,
    offset: int = 0,
) -> ReportListResult:
    ticker = get_ticker_by_symbol(db, symbol)
    if ticker is None:
        return ReportListResult(ticker=None, items=[], total=0)

    filters = [AiReport.ticker_id == ticker.id]
    query = select(AiReport).where(*filters)
    count_query = select(func.count()).select_from(AiReport).where(*filters)
    items = list(
        db.execute(
            query.order_by(desc(AiReport.created_at)).limit(limit).offset(offset)
        ).scalars()
    )
    total = db.execute(count_query).scalar_one()
    return ReportListResult(ticker=ticker, items=items, total=total)


def create_ai_report(
    db: Session,
    *,
    ticker: Ticker,
    report_date: date,
    report_type: str,
    summary: str,
    trend_insights: list[str],
    anomaly_explanations: list[str],
    risk_notes: list[str],
    metrics_snapshot: dict[str, Any],
    model: str,
) -> AiReport:
    report = AiReport(
        ticker_id=ticker.id,
        report_date=report_date,
        report_type=report_type,
        summary=summary,
        trend_insights=trend_insights,
        anomaly_explanations=anomaly_explanations,
        risk_notes=risk_notes,
        metrics_snapshot=metrics_snapshot,
        model=model,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report
