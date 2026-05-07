import logging
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models import EtlJob, EtlStatus
from app.repositories.market_data import load_ticker_prices, upsert_computed_metrics
from app.services.analytics import compute_metrics
from app.services.market_data import MarketDataRequest, get_market_data_provider
from app.services.transforms import clean_price_history

logger = logging.getLogger(__name__)


def list_etl_jobs(
    db: Session,
    *,
    status: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> list[EtlJob]:
    query = select(EtlJob)
    if status:
        query = query.where(EtlJob.status == status)
    query = query.order_by(desc(EtlJob.created_at)).limit(limit).offset(offset)
    return list(db.execute(query).scalars())


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _job_metadata(
    *,
    provider_name: str,
    start_date: date | None,
    end_date: date | None,
    completed_symbols: list[str] | None = None,
    failed_symbols: dict[str, str] | None = None,
    metric_rows_loaded: int = 0,
) -> dict[str, Any]:
    return {
        "provider": provider_name,
        "start_date": start_date.isoformat() if start_date else None,
        "end_date": end_date.isoformat() if end_date else None,
        "completed_symbols": completed_symbols or [],
        "failed_symbols": failed_symbols or {},
        "metric_rows_loaded": metric_rows_loaded,
    }


def _create_job(
    db: Session,
    *,
    symbols: list[str],
    provider_name: str,
    start_date: date | None,
    end_date: date | None,
) -> EtlJob:
    job = EtlJob(
        job_type="market_data",
        status=EtlStatus.RUNNING.value,
        symbols=symbols,
        started_at=_utc_now(),
        metadata_json=_job_metadata(
            provider_name=provider_name,
            start_date=start_date,
            end_date=end_date,
        ),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def _update_job_progress(
    db: Session,
    job: EtlJob,
    *,
    rows_extracted: int,
    rows_loaded: int,
    completed_symbols: list[str],
    failed_symbols: dict[str, str],
    metric_rows_loaded: int,
    provider_name: str,
    start_date: date | None,
    end_date: date | None,
) -> None:
    job.rows_extracted = rows_extracted
    job.rows_loaded = rows_loaded
    job.metadata_json = _job_metadata(
        provider_name=provider_name,
        start_date=start_date,
        end_date=end_date,
        completed_symbols=completed_symbols,
        failed_symbols=failed_symbols,
        metric_rows_loaded=metric_rows_loaded,
    )
    db.commit()


def _mark_job_succeeded(db: Session, job: EtlJob, rows_extracted: int, rows_loaded: int) -> EtlJob:
    job.status = EtlStatus.SUCCEEDED.value
    job.rows_extracted = rows_extracted
    job.rows_loaded = rows_loaded
    job.finished_at = _utc_now()
    db.commit()
    db.refresh(job)
    return job


def _mark_job_failed(
    db: Session,
    job_id: int,
    *,
    error_message: str,
    rows_extracted: int,
    rows_loaded: int,
    provider_name: str,
    start_date: date | None,
    end_date: date | None,
    completed_symbols: list[str],
    failed_symbols: dict[str, str],
    metric_rows_loaded: int,
) -> EtlJob:
    persisted_job = db.execute(select(EtlJob).where(EtlJob.id == job_id)).scalar_one()
    persisted_job.status = EtlStatus.FAILED.value
    persisted_job.error_message = error_message
    persisted_job.rows_extracted = rows_extracted
    persisted_job.rows_loaded = rows_loaded
    persisted_job.finished_at = _utc_now()
    persisted_job.metadata_json = _job_metadata(
        provider_name=provider_name,
        start_date=start_date,
        end_date=end_date,
        completed_symbols=completed_symbols,
        failed_symbols=failed_symbols,
        metric_rows_loaded=metric_rows_loaded,
    )
    db.commit()
    db.refresh(persisted_job)
    return persisted_job

async def run_market_data_etl(
    db: Session,
    settings: Settings,
    symbols: list[str] | None,
    start_date: date | None,
    end_date: date | None,
) -> EtlJob:
    normalized_symbols = [s.upper() for s in (symbols or settings.default_symbol_list)]
    provider = get_market_data_provider(
        settings.market_data_provider,
        timeout_seconds=settings.market_data_timeout_seconds,
        retries=settings.market_data_retries,
        stooq_api_key=settings.stooq_api_key,
    )
    job = _create_job(
        db,
        symbols=normalized_symbols,
        provider_name=provider.source,
        start_date=start_date,
        end_date=end_date,
    )
    rows_extracted = 0
    rows_loaded = 0
    metric_rows_loaded = 0
    completed_symbols: list[str] = []
    failed_symbols: dict[str, str] = {}

    try:
        for symbol in normalized_symbols:
            try:
                logger.info("Running ETL for %s", symbol)
                result = await provider.fetch_history(
                    MarketDataRequest(symbol=symbol, start_date=start_date, end_date=end_date)
                )
                raw_prices = result.rows
                prices = clean_price_history(raw_prices)
                metrics = compute_metrics(prices)
                rows_extracted += len(prices)
                load_result = load_ticker_prices(db, symbol, prices)
                rows_loaded += load_result.rows_submitted
                metric_load_result = upsert_computed_metrics(db, load_result.ticker, metrics)
                metric_rows_loaded += metric_load_result.rows_submitted
                completed_symbols.append(symbol)
                _update_job_progress(
                    db,
                    job,
                    rows_extracted=rows_extracted,
                    rows_loaded=rows_loaded,
                    completed_symbols=completed_symbols,
                    failed_symbols=failed_symbols,
                    metric_rows_loaded=metric_rows_loaded,
                    provider_name=provider.source,
                    start_date=start_date,
                    end_date=end_date,
                )
            except Exception as exc:
                db.rollback()
                failed_symbols[symbol] = str(exc)
                logger.exception("ETL failed for symbol %s", symbol)
                raise

        return _mark_job_succeeded(db, job, rows_extracted, rows_loaded)
    except Exception as exc:
        db.rollback()
        logger.exception("ETL job %s failed", job.id)
        return _mark_job_failed(
            db,
            job.id,
            error_message=str(exc),
            rows_extracted=rows_extracted,
            rows_loaded=rows_loaded,
            provider_name=provider.source,
            start_date=start_date,
            end_date=end_date,
            completed_symbols=completed_symbols,
            failed_symbols=failed_symbols,
            metric_rows_loaded=metric_rows_loaded,
        )
