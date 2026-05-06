# Interview Guide

## 60-Second Pitch

I built a capital markets reporting platform that ingests historical market data, normalizes it through an ETL pipeline, stores it in PostgreSQL, computes reusable analytics, and exposes the results through FastAPI and a Next.js dashboard. The AI layer generates analyst-style reports from structured metrics rather than raw prompts, so the reports are grounded in data the system has already validated.

## System Design Talking Points

- The system is a modular monolith because that is the right scale for a 1-2 week project and mirrors many internal bank tools.
- PostgreSQL is the source of truth for both raw normalized prices and computed metrics.
- ETL jobs are tracked so failures are observable and recoverable.
- Metrics are persisted to avoid recomputation and to make report generation reproducible.
- AI is intentionally downstream of ETL and analytics, not a data source.

## Tradeoffs

- Daily historical data is enough for the first version; intraday data would add provider cost and more complex storage.
- A synchronous ETL endpoint is acceptable for a portfolio project, but the service boundary allows adding Celery/RQ later.
- Authentication is deferred because the project goal is data/backend depth, not enterprise identity plumbing.
- Stooq/free provider support is practical for local demos; the provider abstraction can support paid market feeds later.

## BMO-Relevant Framing

- React dashboard for internal stakeholders.
- FastAPI REST layer for reusable market data access.
- Python/Pandas ETL pipeline for data processing.
- PostgreSQL schema and indexing for reliable analytics access.
- AI reporting that supports analyst workflow without hiding the underlying metrics.

