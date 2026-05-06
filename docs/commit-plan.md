# 30 Commit Build Plan

Use this sequence to build the project in a way that tells a strong engineering story.

1. Initialize monorepo with backend, frontend, Docker, and environment scaffolding.
2. Add FastAPI app factory, health route, settings, logging, and CORS configuration.
3. Add SQLAlchemy database engine, session lifecycle, and declarative base.
4. Add normalized SQLAlchemy models for tickers, prices, metrics, reports, and ETL jobs.
5. Add Alembic configuration and initial migration with indexes and constraints.
6. Add Pydantic request/response schemas and API error helpers.
7. Add market data provider interface and Stooq/Yahoo-compatible extraction adapter.
8. Add ETL job creation, status transitions, timestamps, and error persistence.
9. Add price transformation pipeline with cleaning, date normalization, and validation.
10. Add duplicate-safe PostgreSQL upserts for tickers and historical prices.
11. Add analytics computation for returns, volatility, moving averages, drawdown, and volume ratio.
12. Persist computed metrics with conflict handling and metric-date uniqueness.
13. Implement `POST /etl/run` and `GET /etl/status`.
14. Implement `GET /tickers` with filtering and pagination.
15. Implement `GET /market-data/{symbol}` with date range and pagination.
16. Implement `GET /metrics/{symbol}` with latest and historical views.
17. Implement `GET /top-movers` using stored metrics and indexed sorting.
18. Add service tests for analytics calculations on deterministic fixture data.
19. Add API tests for ticker, market-data, metrics, ETL status, and validation errors.
20. Add AI report schema and structured metric snapshot builder.
21. Add OpenAI report provider with structured output parsing and graceful fallback.
22. Implement `POST /reports/generate` and `GET /reports/{symbol}`.
23. Add frontend Next.js app shell, Tailwind theme, and API client.
24. Add ticker search and market data chart with loading and error states.
25. Add metrics summary panel and top movers table.
26. Add AI report generation panel with persisted report history.
27. Add ETL status panel and manual ETL trigger flow.
28. Add Docker Compose polish, health checks, and local setup docs.
29. Add GitHub Actions for backend tests, frontend linting, and type checks.
30. Finalize recruiter-facing README, architecture notes, resume bullets, and interview guide.

## Suggested Branch Strategy

- `main`: stable project.
- `feature/backend-foundation`: commits 2-6.
- `feature/etl-analytics`: commits 7-19.
- `feature/ai-reporting`: commits 20-22.
- `feature/frontend-dashboard`: commits 23-27.
- `feature/infrastructure-docs`: commits 28-30.

