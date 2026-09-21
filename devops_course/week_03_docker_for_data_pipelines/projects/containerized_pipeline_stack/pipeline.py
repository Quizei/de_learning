"""
pipeline.py — Containerized Pipeline Stack Demo
================================================
This pipeline demonstrates how a real containerized Python app:
  1. Reads configuration from environment variables (never hardcoded)
  2. Connects to Postgres using SQLAlchemy (with retry logic)
  3. Creates the schema if it doesn't exist
  4. Records each pipeline run in a tracking table
  5. Processes "data" (simulated here for portability)
  6. Prints structured log messages (visible in docker-compose logs)

Run directly (outside Docker, DB must be accessible):
  DB_HOST=localhost DB_USER=pipeline_user DB_PASSWORD=test \\
    DB_NAME=pipeline_db python pipeline.py

Run via docker-compose:
  docker-compose up -d
  docker-compose logs -f pipeline
"""

import os
import sys
import time
import random
from datetime import datetime, timezone

import sqlalchemy
from sqlalchemy import text


# ──────────────────────────────────────────────────────────────
# CONFIGURATION — all from environment variables
# ──────────────────────────────────────────────────────────────

def get_config():
    """Read configuration from environment variables.

    Never hardcode these values in source code.
    Set them via .env file or docker-compose env_file.
    """
    return {
        "db_host":     os.environ.get("DB_HOST", "localhost"),
        "db_port":     int(os.environ.get("DB_PORT", "5432")),
        "db_name":     os.environ.get("DB_NAME", "pipeline_db"),
        "db_user":     os.environ.get("DB_USER", "pipeline_user"),
        "db_password": os.environ.get("DB_PASSWORD", ""),
    }


def build_db_url(config):
    """Build the SQLAlchemy database URL from config."""
    return (
        f"postgresql+psycopg2://"
        f"{config['db_user']}:{config['db_password']}"
        f"@{config['db_host']}:{config['db_port']}"
        f"/{config['db_name']}"
    )


# ──────────────────────────────────────────────────────────────
# CONNECTION — with retry loop
# ──────────────────────────────────────────────────────────────

def connect_with_retry(db_url, max_retries=10, delay_seconds=3):
    """Connect to the database with retries.

    Why this matters in Docker:
      Even with depends_on: condition: service_healthy, there's a small
      window where Postgres is marked healthy but not yet fully ready
      for connections. Retry logic makes the pipeline resilient.

    Without this: pipeline fails on the first retry and docker-compose
    restarts it. With this: pipeline waits gracefully.
    """
    log("INFO", f"Connecting to database at {db_url.split('@')[1]}")  # hide credentials

    for attempt in range(1, max_retries + 1):
        try:
            engine = sqlalchemy.create_engine(
                db_url,
                # Pool settings: keep 1 connection, don't pre-connect
                pool_size=2,
                max_overflow=0,
                pool_pre_ping=True,  # check connection health before using
            )
            # Test the connection
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))

            log("INFO", f"Connected to database (attempt {attempt}/{max_retries})")
            return engine

        except Exception as e:
            if attempt < max_retries:
                log("WARN", f"Connection attempt {attempt}/{max_retries} failed: {e}")
                log("INFO", f"Retrying in {delay_seconds}s...")
                time.sleep(delay_seconds)
            else:
                log("ERROR", f"All {max_retries} connection attempts failed")
                raise


# ──────────────────────────────────────────────────────────────
# SCHEMA — create tables if they don't exist
# ──────────────────────────────────────────────────────────────

CREATE_PIPELINE_RUNS_TABLE = """
CREATE TABLE IF NOT EXISTS pipeline_runs (
    id              SERIAL PRIMARY KEY,
    run_id          VARCHAR(64)  NOT NULL,
    pipeline_name   VARCHAR(128) NOT NULL,
    started_at      TIMESTAMPTZ  NOT NULL,
    finished_at     TIMESTAMPTZ,
    status          VARCHAR(32)  NOT NULL DEFAULT 'running',
    rows_processed  INTEGER      DEFAULT 0,
    rows_failed     INTEGER      DEFAULT 0,
    message         TEXT
);

CREATE INDEX IF NOT EXISTS idx_pipeline_runs_pipeline_name
    ON pipeline_runs (pipeline_name);

CREATE INDEX IF NOT EXISTS idx_pipeline_runs_started_at
    ON pipeline_runs (started_at DESC);
"""


def ensure_schema(engine):
    """Create the pipeline_runs table if it doesn't exist.

    This is idempotent: safe to run on every pipeline start.
    In production, you'd use a migration tool (Alembic, Flyway).
    """
    log("INFO", "Ensuring database schema exists")
    with engine.connect() as conn:
        conn.execute(text(CREATE_PIPELINE_RUNS_TABLE))
        conn.commit()
    log("INFO", "Schema ready")


# ──────────────────────────────────────────────────────────────
# PIPELINE LOGIC
# ──────────────────────────────────────────────────────────────

def start_run(engine, pipeline_name):
    """Record the start of a pipeline run. Returns the run_id."""
    import uuid
    run_id = str(uuid.uuid4())[:8]  # short unique ID for this run
    started_at = datetime.now(timezone.utc)

    with engine.connect() as conn:
        conn.execute(
            text("""
                INSERT INTO pipeline_runs (run_id, pipeline_name, started_at, status)
                VALUES (:run_id, :pipeline_name, :started_at, 'running')
            """),
            {
                "run_id": run_id,
                "pipeline_name": pipeline_name,
                "started_at": started_at,
            }
        )
        conn.commit()

    log("INFO", f"run_id={run_id} pipeline={pipeline_name} started")
    return run_id, started_at


def process_data(rows_count=100):
    """Simulate data processing.

    In a real pipeline, this would:
      - Extract from a source (S3, API, Kafka, upstream DB)
      - Transform (clean, validate, aggregate)
      - Load to destination (data warehouse, downstream DB)

    Here we simulate by sleeping and generating random metrics.
    """
    log("INFO", f"Extracting {rows_count} rows from source")
    time.sleep(0.5)  # simulate extraction time

    # Simulate some rows failing validation
    rows_failed = random.randint(0, max(1, rows_count // 20))
    rows_processed = rows_count - rows_failed

    log("INFO", f"Transforming {rows_count} rows (dropped {rows_failed} invalid rows)")
    time.sleep(0.3)  # simulate transformation

    log("INFO", f"Loading {rows_processed} rows to destination")
    time.sleep(0.2)  # simulate load

    return rows_processed, rows_failed


def finish_run(engine, run_id, pipeline_name, rows_processed, rows_failed, status, message=""):
    """Record the completion of a pipeline run."""
    finished_at = datetime.now(timezone.utc)

    with engine.connect() as conn:
        conn.execute(
            text("""
                UPDATE pipeline_runs
                SET finished_at    = :finished_at,
                    status         = :status,
                    rows_processed = :rows_processed,
                    rows_failed    = :rows_failed,
                    message        = :message
                WHERE run_id = :run_id
            """),
            {
                "run_id":         run_id,
                "finished_at":    finished_at,
                "status":         status,
                "rows_processed": rows_processed,
                "rows_failed":    rows_failed,
                "message":        message,
            }
        )
        conn.commit()

    log("INFO", (
        f"run_id={run_id} pipeline={pipeline_name} "
        f"status={status} "
        f"rows_processed={rows_processed} "
        f"rows_failed={rows_failed}"
    ))


def show_recent_runs(engine, limit=5):
    """Query and display the most recent pipeline runs."""
    log("INFO", f"Recent pipeline runs (last {limit}):")

    with engine.connect() as conn:
        result = conn.execute(
            text("""
                SELECT
                    run_id,
                    pipeline_name,
                    started_at AT TIME ZONE 'UTC' AS started_utc,
                    status,
                    rows_processed,
                    rows_failed
                FROM pipeline_runs
                ORDER BY started_at DESC
                LIMIT :limit
            """),
            {"limit": limit}
        )
        rows = result.fetchall()

    if not rows:
        log("INFO", "  No runs recorded yet")
        return

    print()
    print(f"  {'RUN_ID':<10} {'PIPELINE':<25} {'STARTED (UTC)':<22} {'STATUS':<12} {'ROWS':>8} {'FAILED':>8}")
    print("  " + "-" * 95)
    for row in rows:
        started = row.started_utc.strftime("%Y-%m-%d %H:%M:%S") if row.started_utc else "N/A"
        print(
            f"  {row.run_id:<10} "
            f"{row.pipeline_name:<25} "
            f"{started:<22} "
            f"{row.status:<12} "
            f"{row.rows_processed or 0:>8} "
            f"{row.rows_failed or 0:>8}"
        )
    print()


# ──────────────────────────────────────────────────────────────
# LOGGING
# ──────────────────────────────────────────────────────────────

def log(level, message):
    """Structured log line: timestamp [LEVEL] message.

    With PYTHONUNBUFFERED=1 in the Dockerfile, this appears
    immediately in 'docker-compose logs -f pipeline'.
    """
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    print(f"{ts} [{level:<5}] {message}", flush=True)


# ──────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────

def main():
    log("INFO", "=" * 55)
    log("INFO", "Containerized Pipeline Stack — Demo Run")
    log("INFO", "=" * 55)

    # Read configuration
    config = get_config()
    log("INFO", (
        f"Config: host={config['db_host']} "
        f"port={config['db_port']} "
        f"db={config['db_name']} "
        f"user={config['db_user']}"
    ))

    # Connect (with retry for Docker startup timing)
    db_url = build_db_url(config)
    try:
        engine = connect_with_retry(db_url)
    except Exception as e:
        log("ERROR", f"Could not connect to database: {e}")
        log("ERROR", "Check DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME in .env")
        sys.exit(1)

    # Ensure schema exists
    try:
        ensure_schema(engine)
    except Exception as e:
        log("ERROR", f"Schema creation failed: {e}")
        sys.exit(1)

    # Run the pipeline
    pipeline_name = os.environ.get("PIPELINE_NAME", "demo_etl_pipeline")
    rows_to_process = int(os.environ.get("PIPELINE_BATCH_SIZE", "500"))

    run_id, started_at = start_run(engine, pipeline_name)

    try:
        rows_processed, rows_failed = process_data(rows_count=rows_to_process)
        status = "success" if rows_failed == 0 else "partial_success"
        finish_run(engine, run_id, pipeline_name, rows_processed, rows_failed, status)

    except Exception as e:
        log("ERROR", f"Pipeline failed: {e}")
        finish_run(engine, run_id, pipeline_name, 0, 0, "failed", message=str(e))
        sys.exit(1)

    # Show recent history
    show_recent_runs(engine, limit=5)

    log("INFO", "Pipeline complete. See results with: make psql")
    log("INFO", "  SELECT * FROM pipeline_runs ORDER BY started_at DESC LIMIT 10;")


if __name__ == "__main__":
    main()
