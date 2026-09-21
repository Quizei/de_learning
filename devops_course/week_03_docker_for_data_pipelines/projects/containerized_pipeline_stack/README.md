# Containerized Pipeline Stack

A complete, runnable local data stack demonstrating Docker best practices
for Python data pipelines.

## What This Is

Two services coordinated by docker-compose:
- **postgres** — PostgreSQL 15 with named volume, healthcheck, and .env config
- **pipeline** — Python ETL app that connects to Postgres, records run metadata

The pipeline creates a `pipeline_runs` table and inserts a record each time it runs.

## Prerequisites

- Docker Desktop installed and running
- `make` available (comes with macOS, `sudo apt install make` on Ubuntu)

## One-Command Setup

```bash
cp .env.example .env
# Edit .env — change DB_PASSWORD and POSTGRES_PASSWORD to any value you like

make up
```

That's it. Postgres starts, the pipeline waits for it to be healthy, then runs.

## Watch It Work

```bash
make logs          # watch all services — see the pipeline run
make logs-pipeline # watch only the pipeline output
```

Expected pipeline output:
```
2024-06-10 10:00:01 [INFO ] ═══════════════════════════════
2024-06-10 10:00:01 [INFO ] Containerized Pipeline Stack — Demo Run
2024-06-10 10:00:01 [INFO ] Config: host=postgres port=5432 ...
2024-06-10 10:00:04 [INFO ] Connected to database (attempt 1/10)
2024-06-10 10:00:04 [INFO ] Ensuring database schema exists
2024-06-10 10:00:04 [INFO ] run_id=a1b2c3d4 pipeline=demo_etl_pipeline started
2024-06-10 10:00:04 [INFO ] Extracting 500 rows from source
2024-06-10 10:00:05 [INFO ] Transforming 500 rows (dropped 12 invalid rows)
2024-06-10 10:00:05 [INFO ] Loading 488 rows to destination
2024-06-10 10:00:05 [INFO ] run_id=a1b2c3d4 status=partial_success rows_processed=488
```

## Inspect the Database

```bash
make psql
```

Opens a psql session inside the Postgres container. Then run:
```sql
-- See all pipeline runs
SELECT * FROM pipeline_runs ORDER BY started_at DESC;

-- Count runs by status
SELECT status, COUNT(*) FROM pipeline_runs GROUP BY status;

-- Latest run details
SELECT run_id, pipeline_name, started_at, status, rows_processed
FROM pipeline_runs
ORDER BY started_at DESC
LIMIT 1;

-- Exit psql
\q
```

## Run the Pipeline Again

```bash
make run
```

Each run inserts a new record into `pipeline_runs`. Run it multiple times and
inspect the table to see the history build up.

## File Structure

```
containerized_pipeline_stack/
  Dockerfile          — Python 3.11-slim, layer cache, non-root user
  docker-compose.yml  — postgres + pipeline, healthcheck, named volume
  pipeline.py         — ETL app: reads env vars, connects DB, records runs
  Makefile            — shortcut commands
  .env.example        — config template (commit this)
  .env                — your local config with real values (NEVER commit)
```

## Makefile Commands

| Command            | What it does                                    |
|--------------------|------------------------------------------------|
| `make up`          | Build images + start all services               |
| `make down`        | Stop services (data volume preserved)           |
| `make clean`       | Stop services + delete data volumes             |
| `make logs`        | Follow all service logs                         |
| `make logs-pipeline` | Follow pipeline logs only                    |
| `make psql`        | Open psql inside the Postgres container         |
| `make run`         | Run the pipeline once in a new container        |
| `make shell`       | Open bash in a pipeline container               |
| `make ps`          | Show service status                             |
| `make rebuild`     | Force full rebuild without cache                |
| `make help`        | Show all available commands                     |

## Key Concepts Demonstrated

**Layer caching:** `requirements.txt` is copied and installed before
`COPY . .` — so code changes don't trigger a pip reinstall.

**Health checks:** The pipeline waits for `pg_isready` to succeed before
connecting — no more "connection refused" on startup.

**Service DNS:** `DB_HOST=postgres` in `.env` — the service name resolves
to the postgres container IP inside the Docker network.

**Retry logic:** `pipeline.py` retries the DB connection up to 10 times
with 3-second delays — resilient to slow Postgres startup.

**Non-root user:** The Dockerfile creates `appuser` and switches to it
before `CMD` — runs without root privileges.

**Secrets via env:** No credentials in `Dockerfile` or `docker-compose.yml`.
Everything comes from `.env` at runtime.
