# Database Migrations

Alembic owns PostgreSQL schema changes for the FastAPI backend.

## Common Commands

Run migrations:

```bash
alembic upgrade head
```

Create a migration after model changes:

```bash
alembic revision --autogenerate -m "describe change"
```

Rollback one migration:

```bash
alembic downgrade -1
```

## Project Rules

- Keep SQLAlchemy models and Alembic migrations in sync.
- Name important constraints explicitly so upserts and debugging remain predictable.
- Use database-level checks for financial data invariants such as non-negative prices and valid ETL states.
- Do not rely on the API layer alone for duplicate prevention; unique constraints belong in PostgreSQL.

