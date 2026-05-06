"""initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-05-06
"""

from alembic import op
import sqlalchemy as sa

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tickers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("symbol", sa.String(length=16), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("asset_type", sa.String(length=32), nullable=False),
        sa.Column("exchange", sa.String(length=32), nullable=True),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("symbol"),
    )
    op.create_index("ix_tickers_symbol", "tickers", ["symbol"])

    op.create_table(
        "historical_prices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ticker_id", sa.Integer(), sa.ForeignKey("tickers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("price_date", sa.Date(), nullable=False),
        sa.Column("open", sa.Numeric(18, 6), nullable=False),
        sa.Column("high", sa.Numeric(18, 6), nullable=False),
        sa.Column("low", sa.Numeric(18, 6), nullable=False),
        sa.Column("close", sa.Numeric(18, 6), nullable=False),
        sa.Column("adjusted_close", sa.Numeric(18, 6), nullable=True),
        sa.Column("volume", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("ticker_id", "price_date", "source", name="uq_price_ticker_date_source"),
    )
    op.create_index("ix_prices_ticker_date", "historical_prices", ["ticker_id", "price_date"])
    op.create_index("ix_prices_date", "historical_prices", ["price_date"])

    op.create_table(
        "computed_metrics",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ticker_id", sa.Integer(), sa.ForeignKey("tickers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("metric_date", sa.Date(), nullable=False),
        sa.Column("daily_return", sa.Numeric(18, 8), nullable=True),
        sa.Column("weekly_return", sa.Numeric(18, 8), nullable=True),
        sa.Column("monthly_return", sa.Numeric(18, 8), nullable=True),
        sa.Column("volatility_20d", sa.Numeric(18, 8), nullable=True),
        sa.Column("sma_20", sa.Numeric(18, 6), nullable=True),
        sa.Column("sma_50", sa.Numeric(18, 6), nullable=True),
        sa.Column("ema_20", sa.Numeric(18, 6), nullable=True),
        sa.Column("drawdown", sa.Numeric(18, 8), nullable=True),
        sa.Column("volume_ratio_20d", sa.Numeric(18, 8), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("ticker_id", "metric_date", name="uq_metric_ticker_date"),
    )
    op.create_index("ix_metrics_ticker_date", "computed_metrics", ["ticker_id", "metric_date"])
    op.create_index("ix_metrics_date_return", "computed_metrics", ["metric_date", "daily_return"])

    op.create_table(
        "ai_reports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ticker_id", sa.Integer(), sa.ForeignKey("tickers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("report_date", sa.Date(), nullable=False),
        sa.Column("report_type", sa.String(length=32), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("trend_insights", sa.JSON(), nullable=False),
        sa.Column("anomaly_explanations", sa.JSON(), nullable=False),
        sa.Column("risk_notes", sa.JSON(), nullable=False),
        sa.Column("metrics_snapshot", sa.JSON(), nullable=False),
        sa.Column("model", sa.String(length=80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_reports_ticker_date", "ai_reports", ["ticker_id", "report_date"])

    op.create_table(
        "etl_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("symbols", sa.JSON(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rows_extracted", sa.Integer(), nullable=False),
        sa.Column("rows_loaded", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_etl_jobs_started_status", "etl_jobs", ["started_at", "status"])


def downgrade() -> None:
    op.drop_table("etl_jobs")
    op.drop_table("ai_reports")
    op.drop_table("computed_metrics")
    op.drop_table("historical_prices")
    op.drop_index("ix_tickers_symbol", table_name="tickers")
    op.drop_table("tickers")

