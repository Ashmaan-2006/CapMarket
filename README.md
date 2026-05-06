# Capital Markets AI Reporting System

Backend-heavy full-stack platform for ingesting market data, computing portfolio-style analytics, and generating grounded analyst reports from structured metrics.

This project is designed as a production-minded internal tool for capital markets analysts, traders, and business stakeholders. It demonstrates ETL design, normalized PostgreSQL data modeling, REST API development, analytics persistence, AI integration, Dockerized infrastructure, and a clean React dashboard.

## Why This Project

Capital markets teams need reliable access to normalized market data, computed metrics, and concise explanations of market movement. This system treats AI as a reporting layer on top of verified metrics, not as a replacement for data engineering.

The system:

- Extracts historical OHLCV data for stocks and ETFs.
- Cleans, normalizes, and incrementally loads prices into PostgreSQL.
- Computes and stores returns, volatility, moving averages, drawdown, volume signals, and top movers.
- Exposes analyst-friendly REST APIs through FastAPI.
- Generates AI reports from structured database metrics.
- Presents ticker search, charts, metrics, ETL status, and report output in a Next.js dashboard.

## Architecture

```text
Market Data Provider
        |
        v
FastAPI ETL Service ----> etl_jobs
        |
        v
Pandas Transform Layer
        |
        v
PostgreSQL
  - tickers
  - historical_prices
  - computed_metrics
  - ai_reports
  - etl_jobs
        |
        v
FastAPI REST API
        |
        v
Next.js Analyst Dashboard
        |
        v
OpenAI/Gemini Report Generation
```

## Tech Stack

- Frontend: Next.js, React, TypeScript, Tailwind CSS, Recharts
- Backend: FastAPI, Pandas, SQLAlchemy 2.x, Pydantic
- Database: PostgreSQL
- AI: OpenAI structured report pipeline, Gemini-ready abstraction
- Infrastructure: Docker, Docker Compose

## Core Features

- Incremental ETL with job tracking, status, timestamps, error capture, and duplicate protection.
- Normalized relational schema with composite unique constraints and practical indexes.
- Stored analytics so dashboard requests do not recompute expensive metrics.
- REST endpoints for tickers, market data, metrics, top movers, ETL, and AI reports.
- AI reports generated from structured metrics snapshots.
- Dockerized local development with separate frontend, backend, and database services.

## API Surface

- `GET /health`
- `GET /tickers`
- `GET /market-data/{symbol}`
- `GET /metrics/{symbol}`
- `GET /top-movers`
- `POST /etl/run`
- `GET /etl/status`
- `GET /reports/{symbol}`
- `POST /reports/generate`

Report endpoints use the same production API conventions as market data:

- `GET /reports/{symbol}` returns `{ symbol, items, limit, offset, count, total }`.
- `POST /reports/generate` creates a stored report from computed metrics and returns `201 Created`.

## Local Development

1. Copy environment values:

```bash
cp .env.example .env
```

2. Start the stack:

```bash
docker compose up --build
```

3. Apply migrations:

```bash
docker compose exec backend alembic upgrade head
```

4. Run an ETL job:

```bash
curl -X POST http://localhost:8000/etl/run \
  -H "Content-Type: application/json" \
  -d '{"symbols":["AAPL","MSFT","SPY","TSLA"],"start_date":"2024-01-01"}'
```

5. Open the dashboard:

```text
http://localhost:3000
```

## Environment Variables

See `.env.example`.

Important values:

- `DATABASE_URL`
- `DB_POOL_SIZE`
- `DB_MAX_OVERFLOW`
- `DB_POOL_TIMEOUT`
- `APP_ENV`
- `LOG_LEVEL`
- `MARKET_DATA_PROVIDER`
- `MARKET_DATA_TIMEOUT_SECONDS`
- `MARKET_DATA_RETRIES`
- `OPENAI_API_KEY`
- `AI_PROVIDER`
- `NEXT_PUBLIC_API_BASE_URL`

## Database Design

See [docs/architecture.md](docs/architecture.md) for the schema, relationships, indexes, and performance notes.
