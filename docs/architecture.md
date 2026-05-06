# System Architecture

## Design Intent

This is a modular monolith, not a microservice project. A single FastAPI backend owns ETL, analytics, reporting, and REST APIs. That keeps the project realistic for a 1-2 week build while still showing production-level boundaries.

## Data Flow

1. A user or scheduled process calls `POST /etl/run`.
2. The backend creates an `etl_jobs` row with status `running`.
3. The extract layer fetches OHLCV price history from a provider.
4. The transform layer normalizes columns, fixes date types, sorts rows, removes invalid rows, and computes analytics with Pandas.
5. The load layer upserts tickers, historical prices, and computed metrics into PostgreSQL.
6. The API serves stored data to the dashboard.
7. `POST /reports/generate` builds a structured metric snapshot and sends only that snapshot to the AI provider.
8. The generated report is stored in `ai_reports`.

## Database Schema

### tickers

Represents a tradeable symbol.

- `id` primary key
- `symbol` unique
- `name`
- `asset_type`
- `exchange`
- `currency`
- `is_active`
- `created_at`
- `updated_at`

### historical_prices

Stores normalized daily OHLCV records.

- `id` primary key
- `ticker_id` foreign key to `tickers.id`
- `price_date`
- `open`
- `high`
- `low`
- `close`
- `adjusted_close`
- `volume`
- `source`
- `created_at`
- `updated_at`

Unique constraint:

- `(ticker_id, price_date, source)`

### computed_metrics

Stores daily computed analytics. These are persisted so API reads remain cheap and consistent.

- `id` primary key
- `ticker_id` foreign key to `tickers.id`
- `metric_date`
- `daily_return`
- `weekly_return`
- `monthly_return`
- `volatility_20d`
- `sma_20`
- `sma_50`
- `ema_20`
- `drawdown`
- `volume_ratio_20d`
- `created_at`
- `updated_at`

Unique constraint:

- `(ticker_id, metric_date)`

### ai_reports

Stores model-generated analyst reports grounded in a metrics snapshot.

- `id` primary key
- `ticker_id` foreign key to `tickers.id`
- `report_date`
- `report_type`
- `summary`
- `trend_insights`
- `anomaly_explanations`
- `risk_notes`
- `metrics_snapshot`
- `model`
- `created_at`

### etl_jobs

Tracks ETL execution for observability.

- `id` primary key
- `job_type`
- `status`
- `symbols`
- `started_at`
- `finished_at`
- `rows_extracted`
- `rows_loaded`
- `error_message`
- `metadata`

## Indexing Strategy

- `tickers.symbol`: unique lookup for API path parameters.
- `historical_prices(ticker_id, price_date DESC)`: chart and market-data time-window queries.
- `historical_prices(price_date DESC)`: cross-ticker daily market scans.
- `computed_metrics(ticker_id, metric_date DESC)`: latest ticker metrics.
- `computed_metrics(metric_date DESC, daily_return DESC)`: top movers.
- `ai_reports(ticker_id, report_date DESC)`: latest report lookup.
- `etl_jobs(started_at DESC, status)`: status dashboard.

## Performance Considerations

- ETL uses bulk upsert operations instead of row-by-row inserts.
- Duplicate protection is enforced at the database layer through unique constraints.
- Metrics are stored and versioned by date instead of computed on dashboard requests.
- API endpoints paginate price and metrics history.
- Top movers are served from indexed computed metrics.
- AI generation uses compact metric snapshots to reduce cost, latency, and hallucination risk.

## AI Reporting Design

The report service builds a JSON-compatible snapshot:

- ticker identity
- latest price and volume
- daily/weekly/monthly returns
- volatility
- moving averages
- drawdown
- volume ratio
- peer ranking context when available

The AI model is instructed to produce structured analyst output:

- daily summary
- anomaly explanations
- trend insights
- risk notes

The system does not send raw historical rows to the model.

## 1-2 Week Scope

Build the durable path first:

- schema
- ETL
- analytics
- API
- reports
- Docker
- dashboard

Defer:

- auth
- streaming jobs
- live intraday data
- portfolio optimization
- complex news ingestion
- separate worker services

