# Capital Markets AI Reporting System

Live app: https://cap-market-pi.vercel.app  
Backend API: https://capmarket-kria.onrender.com/docs

A full-stack market reporting system that ingests stock price data, stores it in PostgreSQL, computes financial metrics, and generates analyst-style AI reports from structured metrics. I built it as a personal learning project that models the kind of internal tool analysts and traders could use to move from raw prices to explainable reports without living in spreadsheets all day. Spreadsheets are useful; they just should not be the entire data platform.

## What It Solves

Market data is easier to reason about when ingestion, storage, analytics, and reporting are separated cleanly. This project breaks that workflow into production-style layers:

- ETL pulls OHLCV price data from a configured provider.
- Pandas transforms and validates the data.
- PostgreSQL stores tickers, historical prices, computed metrics, reports, and ETL job history.
- FastAPI exposes the data through REST endpoints.
- The dashboard displays charts, top movers, ETL status, metrics, and AI reports.
- The AI layer uses stored metrics as input, not raw guesswork.

## Deployment Stack

- Frontend: Vercel, Next.js
- Backend: Render, Dockerized FastAPI
- Database: Supabase PostgreSQL
- Market data: configurable provider (`fixture`, `alpha_vantage`, `stooq`)
- AI reporting: OpenAI API with local fallback behavior

The live deployment currently uses the fixture provider for reliable public demos. Real market data can be enabled with an Alpha Vantage or Stooq key, but free API limits are easy to hit. The system is designed so the provider can change without rewriting the ETL pipeline.

## Tech Stack

- Frontend: Next.js, React, TypeScript, Tailwind CSS, Recharts, lucide-react
- Backend: FastAPI, SQLAlchemy 2.x, Pydantic, Pandas
- Database: PostgreSQL, Alembic migrations
- AI: OpenAI structured report generation
- Infrastructure: Docker, Docker Compose, Render, Vercel, Supabase
- Testing: pytest, Ruff, TypeScript typecheck

## Core Features

- Incremental ETL with job tracking, timestamps, provider metadata, and error capture
- Normalized relational schema for tickers, prices, metrics, reports, and ETL jobs
- Stored analytics for daily returns, weekly returns, monthly returns, volatility, moving averages, drawdown, volume ratio, and top movers
- REST API for dashboard and external consumers
- AI reports generated from structured computed metrics
- Clean dashboard with ticker search, price chart, metrics cards, ETL state, and report panel
- Dockerized local development across frontend, backend, and database

## Architecture

```text
Market Data Provider
        |
        v
FastAPI ETL Service ----> etl_jobs
        |
        v
Pandas Transform + Analytics
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
Next.js Dashboard
        |
        v
OpenAI Report Generation
```

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

See [docs/api-contract.md](docs/api-contract.md) for request and response details.

## Run Locally

1. Clone and configure:

```bash
git clone https://github.com/Ashmaan-2006/CapMarket.git
cd CapMarket
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

4. Open:

```text
Frontend: http://localhost:3000
Backend docs: http://localhost:8000/docs
```

5. Run ETL from the dashboard or API:

```bash
curl -X POST http://localhost:8000/etl/run \
  -H "Content-Type: application/json" \
  -d '{"symbols":["AAPL","MSFT","TSLA"],"start_date":"2024-01-01"}'
```

## Environment

Use `.env.example` as the source of truth. The key values are:

- `DATABASE_URL`
- `MARKET_DATA_PROVIDER`
- `ALPHA_VANTAGE_API_KEY`
- `STOOQ_API_KEY`
- `OPENAI_API_KEY`
- `BACKEND_CORS_ORIGINS`
- `NEXT_PUBLIC_API_BASE_URL`

For a reliable local demo, use:

```env
MARKET_DATA_PROVIDER=fixture
```

For real market data:

```env
MARKET_DATA_PROVIDER=alpha_vantage
ALPHA_VANTAGE_API_KEY=your_key
MARKET_DATA_RETRIES=0
```

Free market-data APIs have sharp limits, so retries are best kept low. The market will not forgive wasted API calls either.

## Fork And Deploy

1. Fork this repository.
2. Create a Supabase PostgreSQL project.
3. Deploy `backend/` to Render as a Docker web service.
4. Set Render environment variables:

```env
DATABASE_URL=postgresql+psycopg://...
APP_ENV=production
MARKET_DATA_PROVIDER=fixture
OPENAI_API_KEY=your_openai_key
BACKEND_CORS_ORIGINS=https://your-vercel-url.vercel.app
PORT=8000
```

5. Deploy `frontend/` to Vercel.
6. Set Vercel environment variable:

```env
NEXT_PUBLIC_API_BASE_URL=https://your-render-backend-url.onrender.com
```

7. Redeploy both services after updating environment variables.

## Quality Checks

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
npm run build
```

## More Docs

- [Architecture](docs/architecture.md)
- [API Contract](docs/api-contract.md)
- [Operations Runbook](docs/runbook.md)
