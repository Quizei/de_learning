"""
Docker for Data Engineers — Docker Compose for Data Stacks
==========================================================
Running one container is easy.
Running five containers that depend on each other is a different problem.

Your typical local data stack needs:
  - Postgres (the database your pipeline reads from and writes to)
  - Redis (cache, job queue)
  - Your pipeline service (reads from Postgres, processes data)
  - Maybe Airflow (orchestrator scheduling your pipeline)
  - Maybe a data quality checker

Without docker-compose, you'd run each container manually, figure out
the right -p, -e, -v flags for each, wait for them to start in the right
order, and hope they can find each other on the network.

docker-compose solves all of this with a single YAML file and one command.

This file covers:
- docker-compose.yml structure with all fields explained
- Service networking: why "postgres" not "localhost"
- depends_on and health checks (the right way to order startup)
- Essential docker-compose commands
- Environment file patterns
- Override files for dev vs prod
- Complete data stack example

Run this file: python3 03_docker_compose_data_stacks.py
"""


# ============================================================
# HELPER
# ============================================================

def section(title):
    print()
    print("=" * 70)
    print(f"  {title}")
    print("=" * 70)


def demo(cmd, note="", explanation=""):
    """Print a docker-compose command with explanation."""
    print(f"\n  $ {cmd}")
    if note:
        print(f"  # {note}")
    if explanation:
        for line in explanation.strip().splitlines():
            print(f"    {line}")


def show_file(filename, content, explanation=""):
    """Display a file with annotations."""
    print(f"\n  File: {filename}")
    print("  " + "-" * 50)
    for line in content.strip().splitlines():
        print(f"  {line}")
    print("  " + "-" * 50)
    if explanation:
        print()
        for line in explanation.strip().splitlines():
            print(f"  {line}")


# ============================================================
# 1. WHY DOCKER COMPOSE?
# ============================================================

section("1. WHY DOCKER COMPOSE?")

print("""
  The data engineer's local dev stack problem:

  To develop and test a pipeline locally, you need:
    1. A Postgres database  (the pipeline's source or sink)
    2. Your pipeline code   (Python app, reads/writes to Postgres)

  Without docker-compose — painful:
    docker run -d --name dev_db -e POSTGRES_USER=user -e POSTGRES_PASSWORD=pass \\
      -e POSTGRES_DB=mydb -p 5432:5432 \\
      -v pgdata:/var/lib/postgresql/data \\
      --network pipeline_net postgres:15

    docker network create pipeline_net
    docker run --rm -e DB_HOST=dev_db -e DB_USER=user \\
      -e DB_PASSWORD=pass --network pipeline_net \\
      my_pipeline:latest

  Every time. Manually. In the right order.
  And if you restart your laptop, you have to redo all of it.

  With docker-compose:
    docker-compose up -d

  One command. Everything starts. Every time.
""")


# ============================================================
# 2. DOCKER-COMPOSE.YML STRUCTURE
# ============================================================

section("2. docker-compose.yml — Full Structure Explained")

COMPOSE_ANNOTATED = """
# docker-compose.yml — A complete data stack
#
# version: field is deprecated in Compose v2+, but still common in examples.
# Docker Compose v2 (which ships with Docker Desktop) ignores it.
# You can omit it entirely in new files.

services:

  # ─────────────────────────────────────────────────────
  #  postgres SERVICE — the database
  # ─────────────────────────────────────────────────────
  postgres:
    image: postgres:15                  # use this image (pulled if not local)
    container_name: pipeline_postgres   # human-readable name (optional)
    restart: unless-stopped             # restart automatically unless you stop it

    environment:                        # environment variables for this container
      POSTGRES_USER: ${DB_USER}         # from .env file (never hardcode)
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${DB_NAME}

    ports:
      - "5432:5432"                     # expose to host (for psql, DBeaver, etc.)

    volumes:
      - postgres_data:/var/lib/postgresql/data  # named volume: data persists

    networks:
      - pipeline_net                    # custom network for inter-service comms

    healthcheck:                        # tell Docker when postgres is actually ready
      test: ["CMD-SHELL", "pg_isready -U ${DB_USER} -d ${DB_NAME}"]
      interval: 5s                      # check every 5 seconds
      timeout: 5s                       # fail if no response in 5s
      retries: 5                        # try 5 times before marking unhealthy
      start_period: 10s                 # give it 10s to start before checking


  # ─────────────────────────────────────────────────────
  #  redis SERVICE — cache / job queue
  # ─────────────────────────────────────────────────────
  redis:
    image: redis:7-alpine
    container_name: pipeline_redis
    restart: unless-stopped
    ports:
      - "6379:6379"
    networks:
      - pipeline_net
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5


  # ─────────────────────────────────────────────────────
  #  pipeline SERVICE — your Python app
  # ─────────────────────────────────────────────────────
  pipeline:
    build:                              # BUILD from Dockerfile (not a pre-built image)
      context: .                        # where to find the Dockerfile
      dockerfile: Dockerfile            # which Dockerfile to use (default: Dockerfile)
    container_name: pipeline_app
    restart: on-failure                 # restart if it crashes (not if you stop it)

    env_file:
      - .env                            # load ALL env vars from .env file

    depends_on:
      postgres:
        condition: service_healthy      # wait until postgres healthcheck passes
      redis:
        condition: service_healthy      # wait until redis is healthy too

    networks:
      - pipeline_net

    volumes:
      - ./data:/app/data                # bind mount for input/output data files

    # Override CMD for development (run interactively)
    # Comment out for production (uses Dockerfile's CMD)
    # command: python -m pytest tests/


# ─────────────────────────────────────────────────────────────
#  VOLUMES — named storage managed by Docker
# ─────────────────────────────────────────────────────────────
volumes:
  postgres_data:                        # Docker manages this volume's location
    driver: local                       # local = stored on this machine


# ─────────────────────────────────────────────────────────────
#  NETWORKS — how containers talk to each other
# ─────────────────────────────────────────────────────────────
networks:
  pipeline_net:
    driver: bridge                      # default network type
"""

show_file("docker-compose.yml", COMPOSE_ANNOTATED)


# ============================================================
# 3. SERVICE NETWORKING — WHY "postgres" NOT "localhost"
# ============================================================

section("3. SERVICE NETWORKING — Why 'postgres' Not 'localhost'")

print("""
  This is one of the most common mistakes when moving from local dev
  (no Docker) to Docker Compose.

  WITHOUT Docker Compose:
    Postgres runs on your machine. From your Python script, you connect to:
      host="localhost"
      port=5432

  WITH Docker Compose:
    Your Python pipeline runs INSIDE a container.
    Postgres runs INSIDE a different container.
    "localhost" inside the pipeline container means THE PIPELINE CONTAINER.
    There's no Postgres on localhost from inside the pipeline container.

  How to connect from the pipeline container to the postgres container:
    host="postgres"   ← the SERVICE NAME in docker-compose.yml

  Why this works:
    Docker Compose creates an internal DNS for your custom network.
    Every service name becomes a hostname.
    "postgres" resolves to the IP address of the postgres container.
    "redis" resolves to the IP address of the redis container.

  ┌─────────────────────────────────────────────────────────────┐
  │  DOCKER NETWORK: pipeline_net                                │
  │                                                             │
  │  ┌──────────────┐  host="postgres"  ┌──────────────────┐  │
  │  │  pipeline    │ ────────────────→ │  postgres        │  │
  │  │  container   │                   │  container       │  │
  │  │              │                   │  (listening 5432)│  │
  │  └──────────────┘                   └──────────────────┘  │
  │                                                             │
  │  From OUTSIDE (your laptop, DBeaver, psql):                 │
  │    host="localhost", port=5432   ← via -p 5432:5432        │
  └─────────────────────────────────────────────────────────────┘

  In your Python pipeline code:
""")

print("""
  WRONG (works locally without Docker, breaks in docker-compose):
    DB_HOST = "localhost"

  RIGHT (works in docker-compose, also works with env vars):
    DB_HOST = os.environ.get("DB_HOST", "localhost")

  Then in .env:
    DB_HOST=postgres   ← service name inside Docker network

  This pattern means your code works BOTH locally (DB_HOST=localhost)
  AND inside Docker (DB_HOST=postgres), just by changing .env.
""")


# ============================================================
# 4. DEPENDS_ON AND HEALTH CHECKS
# ============================================================

section("4. depends_on and Health Checks — Startup Ordering")

print("""
  The problem: Postgres takes 3-10 seconds to start up and be ready
  to accept connections. If your pipeline starts at the same time
  and immediately tries to connect, it fails.

  depends_on: WITHOUT condition — NOT enough:
    depends_on:
      - postgres

  This only waits for the postgres CONTAINER to START, not for Postgres
  to be READY to accept connections. The container starts almost instantly,
  but the database inside takes seconds.

  What happens: pipeline starts, tries to connect while Postgres is still
  initializing, gets "connection refused", pipeline crashes. You restart it.
  This is annoying in development and a real problem in automation.

  The right solution: combine depends_on with healthcheck.
""")

print("""
  STEP 1: Add a healthcheck to the postgres service:

    postgres:
      image: postgres:15
      healthcheck:
        test: ["CMD-SHELL", "pg_isready -U ${DB_USER} -d ${DB_NAME}"]
        interval: 5s       # check every 5 seconds
        timeout: 5s        # fail the check if no response in 5s
        retries: 5         # mark 'unhealthy' after 5 consecutive failures
        start_period: 10s  # don't count failures in the first 10s (startup grace)

  STEP 2: In the pipeline service, depend on 'service_healthy':

    pipeline:
      depends_on:
        postgres:
          condition: service_healthy   # wait until healthcheck passes, not just started

  What 'pg_isready' does:
    It's a small utility bundled with Postgres.
    It connects to Postgres and checks if it accepts connections.
    Returns exit code 0 (success) when Postgres is ready.
    Docker reads the exit code to determine health.

  Similar health checks for other services:

    redis:
      healthcheck:
        test: ["CMD", "redis-cli", "ping"]
        interval: 5s
        timeout: 3s
        retries: 5

    mysql:
      healthcheck:
        test: ["CMD", "mysqladmin", "ping", "-h", "localhost"]
        interval: 10s
        timeout: 5s
        retries: 5
""")

print("""
  Alternative: build retry logic into your pipeline:

    # In pipeline.py
    import time
    import sqlalchemy
    from sqlalchemy import create_engine

    def connect_with_retry(url, max_retries=5, delay=3):
        for attempt in range(1, max_retries + 1):
            try:
                engine = create_engine(url)
                engine.connect()
                return engine
            except Exception as e:
                print(f"Attempt {attempt}/{max_retries} failed: {e}")
                if attempt < max_retries:
                    time.sleep(delay)
        raise RuntimeError("Could not connect after retries")

  Use BOTH: healthcheck (fast path) + retry logic (resilience).
""")


# ============================================================
# 5. ESSENTIAL DOCKER-COMPOSE COMMANDS
# ============================================================

section("5. ESSENTIAL DOCKER-COMPOSE COMMANDS")

demo(
    "docker-compose up -d",
    note="Start all services in the background (detached)",
    explanation="""
  Reads docker-compose.yml in current directory.
  Pulls images if not cached locally.
  Creates networks and volumes if they don't exist.
  Starts all services in dependency order.
  Returns immediately (-d). Containers run in background.
    """
)

demo(
    "docker-compose up --build",
    note="Rebuild images from Dockerfile, then start",
    explanation="""
  Forces docker build for all services with 'build:' in their config.
  Use when you changed your code and want the new version running.
  Without --build: uses the existing built image (might be stale).
    """
)

demo(
    "docker-compose up -d --build pipeline",
    note="Rebuild and restart ONLY the pipeline service",
    explanation="""
  Rebuilds and restarts just the pipeline service.
  Postgres and Redis continue running undisturbed.
  Fastest iteration cycle when only your code changed.
    """
)

demo(
    "docker-compose logs -f",
    note="Follow logs from ALL services (Ctrl+C to stop)",
    explanation="""
  Mixed output from all services, each line prefixed with service name:
    pipeline_app   | 2024-06-10 10:00:01 [INFO] Starting pipeline run
    pipeline_postgres | ... (postgres startup logs)
    pipeline_app   | 2024-06-10 10:00:04 [INFO] Extracted 1000 rows
  -f = follow (live updates). Without -f, shows existing logs and exits.
    """
)

demo(
    "docker-compose logs -f pipeline",
    note="Follow logs from ONE service only",
    explanation="""
  Filter to just the pipeline service's output.
  Much easier to read than mixed multi-service output.
  --tail=50: start from the last 50 lines instead of the beginning.
    """
)

demo(
    "docker-compose exec postgres psql -U pipeline_user -d pipeline_db",
    note="Open psql shell inside the running postgres container",
    explanation="""
  'exec' runs a command in an ALREADY RUNNING container.
  No need to install psql on your machine.
  You'll get a psql prompt: pipeline_db=#
  Run SQL, check tables, inspect data. Exit with \\q.
    """
)

demo(
    "docker-compose ps",
    note="Show status of all services in this compose project",
    explanation="""
  Shows: Name, Command, State, Ports
  State is one of: Up, Up (healthy), Up (unhealthy), Exit 1
  'Exit 1' means your container crashed — check logs immediately.
    """
)

demo(
    "docker-compose stop",
    note="Stop all containers WITHOUT removing them",
    explanation="""
  Containers are stopped but not deleted.
  Named volumes are preserved (your Postgres data is safe).
  Resume with: docker-compose start
  Use this for: "taking a break, picking up where I left off"
    """
)

demo(
    "docker-compose down",
    note="Stop and REMOVE all containers (volumes kept)",
    explanation="""
  Removes containers and the default network.
  Named volumes are PRESERVED — your Postgres data survives.
  Use this for: "done for the day, want a clean state"
  Next 'up' will recreate containers from scratch (volumes still there).
    """
)

demo(
    "docker-compose down -v",
    note="Stop, remove containers AND remove all volumes",
    explanation="""
  -v removes ALL named volumes too.
  Your Postgres data is DELETED. Fresh start.
  Use this for: "reset everything — nuke it from orbit"
  Useful when you want a completely clean dev environment.
    """
)

demo(
    "docker-compose build pipeline",
    note="Rebuild the image for just the 'pipeline' service",
    explanation="""
  Rebuilds the pipeline image without starting containers.
  Useful for: pre-building images before deployment.
    """
)

demo(
    "docker-compose run --rm pipeline python test_connection.py",
    note="Run a one-off command in a new pipeline container",
    explanation="""
  Creates a new container from the pipeline image, runs the command, removes it.
  The compose network and volumes are available.
  Useful for: running tests, migrations, one-off scripts.
  Does NOT start other services — you need them running separately.
    """
)


# ============================================================
# 6. ENVIRONMENT FILES
# ============================================================

section("6. ENVIRONMENT FILES — Per-Service Config")

print("""
  Pattern: one .env file for the whole project (or per service).

  In docker-compose.yml you can reference env vars two ways:
""")

ENV_PATTERNS = """
services:
  postgres:
    image: postgres:15
    environment:
      # Option 1: inline value (hardcoded, bad for secrets)
      POSTGRES_USER: pipeline_user

      # Option 2: reference host environment variable
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}   # from shell or .env file

  pipeline:
    build: .
    # Option 3: load an entire file as environment variables
    env_file:
      - .env               # main config
      - .env.local         # local overrides (gitignored)
"""

print(ENV_PATTERNS)

print("""
  .env file (never commit):
    DB_HOST=postgres
    DB_PORT=5432
    DB_NAME=pipeline_db
    DB_USER=pipeline_user
    DB_PASSWORD=changeme
    POSTGRES_PASSWORD=changeme

  .env.example (commit this, as documentation):
    DB_HOST=postgres
    DB_PORT=5432
    DB_NAME=pipeline_db
    DB_USER=pipeline_user
    DB_PASSWORD=your_password_here
    POSTGRES_PASSWORD=your_password_here

  .gitignore:
    .env
    .env.local
    .env.*.local

  docker-compose automatically loads a .env file from the same directory.
  Variable substitution ${VAR} in docker-compose.yml reads from this file.
""")


# ============================================================
# 7. OVERRIDE FILES
# ============================================================

section("7. Override Files — docker-compose.override.yml")

print("""
  Problem: you want different settings for dev vs CI vs production.
  Dev: mount source code live, expose debug ports, verbose logging.
  CI: run tests, no port exposure, test database.
  Prod: no volumes, strict restart policies, no debug tools.

  Solution: override files.

  docker-compose.yml            — base config (commit to git)
  docker-compose.override.yml   — dev-specific overrides (gitignored or committed)
  docker-compose.ci.yml         — CI overrides
  docker-compose.prod.yml       — prod overrides

  docker-compose automatically merges docker-compose.yml + docker-compose.override.yml.
  For other files, specify explicitly:
    docker-compose -f docker-compose.yml -f docker-compose.ci.yml up
""")

OVERRIDE_EXAMPLE = """
# docker-compose.override.yml — dev overrides
# Automatically merged with docker-compose.yml
services:
  pipeline:
    # Mount source code live — changes immediately without rebuild
    volumes:
      - ./src:/app/src

    # Override command for interactive dev
    command: python -m pytest tests/ -v

    environment:
      LOG_LEVEL: DEBUG

  postgres:
    # Expose Postgres to host in dev (for GUI tools like DBeaver, TablePlus)
    ports:
      - "5432:5432"
"""

show_file("docker-compose.override.yml", OVERRIDE_EXAMPLE)

print("""
  In production (docker-compose.prod.yml), you'd remove port exposure,
  add strict resource limits, and use secrets management instead of .env.
""")


# ============================================================
# 8. COMPLETE DATA STACK EXAMPLE
# ============================================================

section("8. Complete Local Data Stack — One Command Setup")

print("""
  The full workflow:

    cp .env.example .env
    # Edit .env with your desired passwords
    docker-compose up -d --build

  Everything is running. Then:
    docker-compose logs -f              # watch everything start up
    docker-compose logs -f pipeline     # watch pipeline output
    docker-compose exec postgres psql -U pipeline_user -d pipeline_db

  When done:
    docker-compose down                 # keep data
    docker-compose down -v              # nuke everything

  This replaces:
    "install Postgres", "configure it", "create users", "create databases",
    "start it on boot", "manage versions", "share setup instructions with team"

  With docker-compose, the setup instructions ARE the docker-compose.yml file.
  Everyone on the team runs 'docker-compose up' and gets the identical stack.
""")


# ============================================================
# QUICK REFERENCE
# ============================================================

print()
print("=" * 70)
print("  QUICK REFERENCE — docker-compose Commands")
print("=" * 70)
print("""
  START / STOP:
    docker-compose up -d                start all services (background)
    docker-compose up --build           rebuild images then start
    docker-compose up -d --build svc    rebuild + restart one service
    docker-compose stop                 stop (keep containers + volumes)
    docker-compose start                restart stopped services
    docker-compose down                 remove containers (keep volumes)
    docker-compose down -v              remove containers + volumes

  LOGS:
    docker-compose logs -f              follow all services
    docker-compose logs -f service      follow one service
    docker-compose logs --tail=100      last 100 lines

  INSPECT:
    docker-compose ps                   status of all services
    docker-compose exec svc CMD         run command in running container
    docker-compose run --rm svc CMD     run one-off command, remove after

  BUILD:
    docker-compose build service        build one service's image
    docker-compose pull                 pull updated images

  NETWORKING RULE:
    Inside docker-compose, connect to services by SERVICE NAME:
      host = "postgres"  (not "localhost")
      host = "redis"     (not "127.0.0.1")

  HEALTH CHECK PATTERN:
    postgres:
      healthcheck:
        test: ["CMD-SHELL", "pg_isready -U user -d db"]
        interval: 5s
        retries: 5
    pipeline:
      depends_on:
        postgres:
          condition: service_healthy   ← waits for health, not just start
""")
