# Operations Runbook

This runbook covers the commands needed to operate the project locally and verify the main data/reporting workflows.

## Start the Stack

```bash
cp .env.example .env
docker compose up --build
```

Services:

- Frontend: `http://localhost:3000`
- Backend API: `http://localhost:8000`
- API docs in development: `http://localhost:8000/docs`
- PostgreSQL: `localhost:5432`

## Database Migrations

Apply migrations:

```bash
docker compose exec backend alembic upgrade head
```

Check current migration:

```bash
docker compose exec backend alembic current
```

Create a new migration after model changes:

```bash
docker compose exec backend alembic revision --autogenerate -m "describe change"
```

## Health Checks

Liveness:

```bash
curl http://localhost:8000/health
```

Database readiness:

```bash
curl http://localhost:8000/health/ready
```

Every response includes:

- `X-Request-ID`
- `X-Process-Time-ms`

You can pass a request ID explicitly:

```bash
curl http://localhost:8000/health -H "X-Request-ID: local-debug-1"
```

## Run ETL

Trigger an incremental ETL job:

```bash
curl -X POST http://localhost:8000/etl/run \
  -H "Content-Type: application/json" \
  -d '{"symbols":["AAPL","MSFT","SPY","TSLA"],"start_date":"2024-01-01"}'
```

Check ETL status:

```bash
curl http://localhost:8000/etl/status
```

Expected result:

- `status` eventually becomes `succeeded`
- `rows_extracted` and `rows_loaded` are non-zero for symbols with available data
- failures store an `error_message`

## Verify Market Data and Metrics

Fetch stored prices:

```bash
curl "http://localhost:8000/market-data/AAPL?limit=5"
```

Fetch stored metrics:

```bash
curl "http://localhost:8000/metrics/AAPL?limit=5"
```

Fetch top movers:

```bash
curl "http://localhost:8000/top-movers?direction=gainers"
curl "http://localhost:8000/top-movers?direction=losers"
```

## Generate AI Reports

Generate a report from stored computed metrics:

```bash
curl -X POST http://localhost:8000/reports/generate \
  -H "Content-Type: application/json" \
  -d '{"symbol":"AAPL","report_type":"daily"}'
```

Fetch persisted reports:

```bash
curl "http://localhost:8000/reports/AAPL?limit=5"
```

When `OPENAI_API_KEY` is empty, the backend uses the local fallback provider. This keeps the workflow testable without external AI credentials.

## Local Quality Checks

Backend:

```bash
cd backend
python -m pip install -e ".[dev]"
python -m ruff check .
python -m pytest
```

Frontend:

```bash
cd frontend
npm ci
npm run typecheck
```

Docker Compose:

```bash
docker compose config
```

## Troubleshooting

### Backend Cannot Connect to Database

Check database health:

```bash
docker compose ps
docker compose logs db
```

Confirm `.env` contains:

```text
DATABASE_URL=postgresql+psycopg://capital:capital@db:5432/capital_markets
```

### ETL Returns No Rows

Confirm the symbol is supported by the configured provider and the requested date range has market data.

```bash
curl "http://localhost:8000/etl/status?limit=5"
```

If Stooq returns an API-key message, either set:

```text
STOOQ_API_KEY=your_stooq_key
```

or use the deterministic local provider:

```text
MARKET_DATA_PROVIDER=fixture
```

### Frontend Cannot Reach Backend

Confirm:

```text
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
BACKEND_CORS_ORIGINS=http://localhost:3000
```

Then restart the frontend container because Next.js reads public environment values at startup.

### Report Generation Returns 404

Reports require stored computed metrics. Run ETL for the symbol first, then call `POST /reports/generate`.
