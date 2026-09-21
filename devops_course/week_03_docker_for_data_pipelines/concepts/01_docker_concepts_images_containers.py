"""
Docker for Data Engineers — Concepts, Images, and Containers
=============================================================
Docker solves the single most common data engineering headache:
"It works on my machine."

You build a pipeline. It uses Python 3.11, pandas 2.0, and a specific
version of psycopg2. Works perfectly on your laptop. You deploy it to
a server — or send it to a colleague — and it crashes because they
have Python 3.9, a different OS, or missing system libraries.

Docker packages your code AND its entire environment (OS layer,
Python version, all packages, all system libraries) into a single
portable unit called a CONTAINER. The container runs identically
everywhere Docker is installed.

This file covers:
- What Docker is and why it exists
- Images vs Containers (the key mental model)
- Registries: where images live
- Layers: how images are built efficiently
- Essential Docker commands with explanations
- Data engineer use cases

Run this file: python3 01_docker_concepts_images_containers.py
Commands are printed with explanations — no Docker daemon needed.
"""


# ============================================================
# HELPER — print sections and demonstrate docker commands
# ============================================================

def section(title):
    print()
    print("=" * 70)
    print(f"  {title}")
    print("=" * 70)


def demo(cmd, note="", explanation=""):
    """Print a Docker command with its purpose and explanation.

    Since Docker requires Docker Desktop / daemon to be running,
    we print commands rather than executing them. Reading is learning.
    """
    print(f"\n  $ {cmd}")
    if note:
        print(f"  # {note}")
    if explanation:
        for line in explanation.strip().splitlines():
            print(f"    {line}")


# ============================================================
# 1. THE PROBLEM DOCKER SOLVES
# ============================================================

section("1. THE PROBLEM DOCKER SOLVES")

print("""
  The classic scenario:

    You: "My pipeline works perfectly, here's the code."
    Server/colleague: "It crashes on import."
    You: "Works on my machine."
    Server/colleague: *deep breath*

  Why this happens:
    - Different Python versions (you: 3.11, server: 3.9)
    - Different OS (you: macOS, server: Ubuntu 20.04)
    - Missing system libraries (libpq for PostgreSQL, libssl, etc.)
    - Different package versions (pandas 2.0 vs 1.5 have breaking changes)
    - Different environment variables

  What Docker does:
    It packages your code + Python version + all packages +
    all system libraries into one self-contained unit.

    "Runs on my machine" stops being relevant.
    The container IS the machine.

  Analogy:
    Without Docker: you give someone a recipe and hope they have
                    the same oven, pans, and ingredients.
    With Docker:    you give someone the pre-cooked meal. They
                    just need a microwave (Docker).
""")


# ============================================================
# 2. CORE CONCEPTS — IMAGE, CONTAINER, REGISTRY, LAYER
# ============================================================

section("2. CORE CONCEPTS")

print("""
  ┌─────────────────────────────────────────────────────────────┐
  │  IMAGE                                                       │
  │  -------                                                     │
  │  A read-only blueprint/template.                            │
  │  Think of it like a Python CLASS DEFINITION.                │
  │  An image defines: OS layer, Python version, packages,      │
  │  your code, the command to run.                             │
  │                                                              │
  │  You build images. You share images. Images don't "run."    │
  └─────────────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────────────┐
  │  CONTAINER                                                   │
  │  ---------                                                   │
  │  A running instance of an image.                            │
  │  Think of it like an OBJECT (instance of a class).          │
  │  You can run many containers from the same image.           │
  │  Each has its own isolated filesystem, network, and         │
  │  processes. Changes inside a container don't affect the     │
  │  image or other containers.                                 │
  └─────────────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────────────┐
  │  REGISTRY                                                    │
  │  --------                                                    │
  │  A store/repository for images.                             │
  │  Think of it like PyPI — but for Docker images.             │
  │                                                              │
  │  Docker Hub (hub.docker.com) — public, default registry     │
  │    python:3.11-slim, postgres:15, redis:7, etc.             │
  │  AWS ECR — private images for your org's pipelines          │
  │  GCR (Google Container Registry) — Google Cloud             │
  │  GitHub Container Registry (ghcr.io)                        │
  └─────────────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────────────┐
  │  LAYER                                                       │
  │  -----                                                       │
  │  Every instruction in a Dockerfile creates a new layer.     │
  │  Layers are CACHED. If a layer hasn't changed, Docker       │
  │  reuses the cached version instead of rebuilding it.        │
  │                                                              │
  │  Layer 1: Ubuntu 22.04 base OS           (cached)           │
  │  Layer 2: Install Python 3.11            (cached)           │
  │  Layer 3: pip install pandas             (cached)           │
  │  Layer 4: COPY pipeline.py               (rebuilds)         │
  │                                                              │
  │  Change your code → only Layer 4 rebuilds. Seconds, not     │
  │  minutes. Layer caching is Docker's killer feature.         │
  └─────────────────────────────────────────────────────────────┘
""")


# ============================================================
# 3. DOCKER ARCHITECTURE
# ============================================================

section("3. DOCKER ARCHITECTURE")

print("""
  How Docker actually works under the hood:

  ┌──────────────────────────────────────────────────────────────┐
  │  YOUR MACHINE                                                 │
  │                                                              │
  │  ┌─────────────┐    API calls    ┌──────────────────────┐   │
  │  │ Docker CLI  │ ─────────────→  │ Docker Daemon        │   │
  │  │ (docker)    │                 │ (dockerd)            │   │
  │  │             │                 │                      │   │
  │  │ You type    │                 │ Does the actual      │   │
  │  │ commands    │                 │ work: build, run,    │   │
  │  │ here        │                 │ pull, manage         │   │
  │  └─────────────┘                 │ containers           │   │
  │                                  └──────────┬───────────┘   │
  │                                             │               │
  │                                  ┌──────────▼───────────┐   │
  │                                  │ Containers           │   │
  │                                  │  ┌────┐  ┌────┐     │   │
  │                                  │  │ C1 │  │ C2 │     │   │
  │                                  │  └────┘  └────┘     │   │
  │                                  └──────────────────────┘   │
  └──────────────────────────────────────────────────────────────┘
          │                                   ↑
          │ docker pull                        │ docker push
          ▼                                   │
  ┌──────────────────┐
  │ REGISTRY         │
  │ (Docker Hub,     │
  │  ECR, GCR)       │
  │                  │
  │  python:3.11     │
  │  postgres:15     │
  │  redis:7         │
  │  your-pipeline   │
  └──────────────────┘

  Key insight:
    "docker run" checks local cache first. If image not found locally,
    it automatically pulls from the registry, THEN runs it.
    You never have to manually pull — but it's faster if you do.
""")


# ============================================================
# 4. ESSENTIAL COMMANDS — IMAGES
# ============================================================

section("4. ESSENTIAL COMMANDS — Working with Images")

demo(
    "docker pull python:3.11-slim",
    note="Download image from Docker Hub to your local machine",
    explanation="""
  Downloads the python:3.11-slim image.
  'python' = image name, '3.11-slim' = tag (version).
  If you omit the tag, Docker uses 'latest' — avoid this in production,
  'latest' changes over time. Always pin to a specific tag.
    """
)

demo(
    "docker images",
    note="List all images stored locally",
    explanation="""
  Shows: REPOSITORY, TAG, IMAGE ID, CREATED, SIZE
  Example output:
    python       3.11-slim   abc123   2 days ago    130MB
    postgres     15          def456   5 days ago    379MB
    redis        7           ghi789   1 week ago    117MB
    """
)

demo(
    "docker rmi python:3.11-slim",
    note="Remove a local image (rmi = remove image)",
    explanation="""
  Frees up disk space. Can't remove if a container is using it.
  docker image prune    — remove all unused images
  docker system prune   — nuclear option: remove all unused everything
    """
)

demo(
    "docker image history python:3.11-slim",
    note="See all the layers that make up this image",
    explanation="""
  Shows each layer, its size, and the command that created it.
  Useful for debugging and security audits (checking what's in an image).
  Also how you accidentally discover secrets baked into images.
    """
)


# ============================================================
# 5. ESSENTIAL COMMANDS — CONTAINERS
# ============================================================

section("5. ESSENTIAL COMMANDS — Running Containers")

demo(
    'docker run python:3.11-slim python3 -c "print(\'hello from Docker\')"',
    note="Run a one-off command inside a container, then exit",
    explanation="""
  'docker run' = create + start container.
  After the command finishes, the container stops (but still exists).
  This is your "throwaway execution" pattern.
    """
)

demo(
    "docker run --rm python:3.11-slim python3 -c \"import pandas; print(pandas.__version__)\"",
    note="--rm removes the container automatically when it exits",
    explanation="""
  --rm is best practice for one-off commands.
  Without --rm, stopped containers accumulate and waste disk.
  Use --rm for: testing, one-off scripts, CI/CD jobs.
    """
)

demo(
    "docker run -it python:3.11-slim bash",
    note="Open an interactive shell inside the container",
    explanation="""
  -i = interactive (keep stdin open)
  -t = allocate a pseudo-TTY (terminal)
  Combined: -it gives you a real interactive shell session.
  Type 'exit' to leave. The container stops when you exit.
  Use this to explore an image or debug interactively.
    """
)

demo(
    "docker run -d --name my_pipeline pipeline:latest",
    note="Run container in background (detached mode)",
    explanation="""
  -d = detached, runs in background, returns container ID.
  --name = give it a human-readable name (instead of random ID).
  Without --name, Docker generates names like "relaxed_darwin".
  Named containers: easier to manage with docker logs, docker stop.
    """
)

demo(
    "docker ps",
    note="List currently RUNNING containers",
    explanation="""
  Shows: CONTAINER ID, IMAGE, COMMAND, CREATED, STATUS, PORTS, NAMES
  Only shows running containers. Stopped ones are invisible.
    """
)

demo(
    "docker ps -a",
    note="List ALL containers including stopped ones",
    explanation="""
  -a = all (include stopped/exited containers).
  Stopped containers still take up disk space.
  Use 'docker container prune' to remove all stopped containers.
    """
)

demo(
    "docker logs my_pipeline",
    note="View stdout/stderr output from a container",
    explanation="""
  Everything your Python code prints goes here.
  docker logs -f my_pipeline        — follow live (like tail -f)
  docker logs --tail 50 my_pipeline — last 50 lines only
  docker logs --since 1h my_pipeline — logs from last 1 hour
    """
)

demo(
    "docker exec -it my_pipeline bash",
    note="Open a shell in an ALREADY RUNNING container",
    explanation="""
  Unlike 'docker run -it', exec connects to an EXISTING running container.
  The container keeps running when you exit.
  Use this to: inspect files, check environment variables, debug live issues.
  Common pattern: docker exec -it my_pipeline python3 (interactive REPL)
    """
)

demo(
    "docker stop my_pipeline",
    note="Gracefully stop a running container (sends SIGTERM, waits 10s, then SIGKILL)",
    explanation="""
  Gives your app time to clean up (close DB connections, flush buffers).
  If your app doesn't exit within 10s, Docker force-kills it.
  docker stop -t 30 my_pipeline — give it 30s instead of 10s.
    """
)

demo(
    "docker rm my_pipeline",
    note="Remove a stopped container (frees disk space)",
    explanation="""
  Must be stopped first. Use 'docker stop' then 'docker rm'.
  Shortcut: docker rm -f my_pipeline  — force stop AND remove.
  Or combine: docker stop my_pipeline && docker rm my_pipeline
    """
)


# ============================================================
# 6. PORT MAPPING, VOLUMES, ENVIRONMENT VARIABLES
# ============================================================

section("6. PORT MAPPING, VOLUMES, ENVIRONMENT VARIABLES")

print("""
  PORT MAPPING:  -p host_port:container_port
  ─────────────────────────────────────────
  Containers have their own isolated network.
  Postgres inside a container listens on port 5432 INSIDE the container.
  But nothing outside can reach it — it's isolated.

  Port mapping creates a tunnel: -p 5432:5432 means:
    "Forward traffic on my machine's port 5432 to container's port 5432."

  Analogy: like call forwarding. All calls to your office number (5432)
  get forwarded to your home number (also 5432).

  Examples:
    -p 5432:5432    Postgres: same port in/out (convenient)
    -p 8080:80      Web server: your machine's 8080 → container's 80
    -p 9999:8888    Jupyter: your machine's 9999 → container's 8888

  You'd access Postgres at localhost:5432 on your machine.
""")

print("""
  VOLUME MOUNTING:  -v /host/path:/container/path
  ──────────────────────────────────────────────
  Containers have their own isolated filesystem.
  Files created inside a container disappear when the container is removed.

  Volume mounting shares a directory between your machine and the container.
  Changes in either place are immediately visible in both.

  Analogy: like a shared Google Drive folder. Both sides see the same files.

  Examples:
    -v ./data:/app/data         Share your ./data folder with the container
    -v ./src:/app/src           Live code updates without rebuilding the image
    -v pgdata:/var/lib/postgresql/data    Named volume for Postgres data

  Named volumes (pgdata above) are managed by Docker — they survive
  container removal and live in Docker's storage area, not your filesystem.
""")

print("""
  ENVIRONMENT VARIABLES:  -e KEY=VALUE  or  --env-file .env
  ──────────────────────────────────────────────────────────
  Pass config and secrets to containers without baking them into the image.
  This is how 12-factor apps work: code in image, config in environment.

  Examples:
    -e DB_URL=postgres://user:pass@host/db    single variable
    -e PYTHONUNBUFFERED=1                     control Python output buffering
    --env-file .env                           load from a file (NEVER commit .env)

  The --env-file pattern is most common in practice:
    1. Create .env.example with placeholder values (commit this)
    2. Create .env with real values (add to .gitignore, NEVER commit)
    3. Run: docker run --env-file .env my_pipeline:latest
""")


# ============================================================
# 7. CONTAINER LIFECYCLE
# ============================================================

section("7. CONTAINER LIFECYCLE")

print("""
  ┌─────────────┐
  │   REGISTRY  │  ← Images live here (Docker Hub, ECR, GCR)
  │  (remote)   │
  └──────┬──────┘
         │ docker pull  (or happens automatically on docker run)
         ▼
  ┌─────────────┐
  │   IMAGE     │  ← Stored locally after pull
  │  (local)    │
  └──────┬──────┘
         │ docker run
         ▼
  ┌─────────────┐   docker stop    ┌──────────────┐
  │  RUNNING    │ ──────────────→  │   STOPPED    │
  │  CONTAINER  │                  │   CONTAINER  │
  │             │ ←──────────────  │              │
  └──────┬──────┘   docker start   └──────┬───────┘
         │                                │
         │ docker exec -it                │ docker rm
         ▼                                ▼
  [shell session]                    [container gone]
  (container still running)          (data inside lost)

  Key rules:
    1. 'docker run' creates a NEW container every time
    2. 'docker start' restarts an EXISTING stopped container
    3. Data inside a container is lost when 'docker rm' is run
       (unless you used volumes — covered in concept file 04)
    4. 'docker stop' is graceful, 'docker kill' is immediate
""")


# ============================================================
# 8. DATA ENGINEER ANGLE — THROWAWAY POSTGRES
# ============================================================

section("8. DATA ENGINEER ANGLE — Throwaway Local Postgres")

print("""
  Real use case: You need a local Postgres to test your pipeline.

  Without Docker:
    - Install Postgres manually (brew install postgresql or apt-get)
    - Configure pg_hba.conf, create users, create databases
    - Hope it doesn't conflict with your existing Postgres
    - Remember to stop it when you're done
    - Total time: 30-60 minutes

  With Docker:
    One command, zero installation, zero config files.
""")

demo(
    "docker run --rm -e POSTGRES_PASSWORD=testpass -e POSTGRES_DB=mydb -p 5432:5432 postgres:15",
    note="Throwaway Postgres 15: deleted when stopped, ready in ~5 seconds",
    explanation="""
  POSTGRES_PASSWORD  — required, sets the postgres superuser password
  POSTGRES_DB        — creates this database on startup (optional)
  -p 5432:5432       — access at localhost:5432 from your machine
  --rm               — container removed when stopped (throwaway)

  Connect from Python:
    sqlalchemy.create_engine("postgresql://postgres:testpass@localhost/mydb")

  Connect from psql:
    psql -h localhost -U postgres -d mydb

  Stop it when done: Ctrl+C (or docker stop <name> if running -d).
  No cleanup needed — --rm handles it.
    """
)

demo(
    "docker run -d --name dev_postgres -e POSTGRES_PASSWORD=testpass -e POSTGRES_DB=pipeline_dev -p 5432:5432 -v pgdata:/var/lib/postgresql/data postgres:15",
    note="Persistent Postgres: data survives container restarts",
    explanation="""
  -d          — detached, runs in background
  --name      — named so you can 'docker stop dev_postgres'
  -v pgdata:  — named volume keeps your data when container is removed
  Stop:  docker stop dev_postgres
  Start: docker start dev_postgres   (data still there)
  Nuke:  docker rm dev_postgres && docker volume rm pgdata
    """
)

demo(
    "docker exec -it dev_postgres psql -U postgres -d pipeline_dev",
    note="Open psql directly inside the running Postgres container",
    explanation="""
  No psql installed on your machine? No problem.
  psql is already inside the Postgres container.
  docker exec runs a command in an existing container.
    """
)

print("""
  This pattern applies to any database or service:
    Redis:     docker run --rm -p 6379:6379 redis:7
    MySQL:     docker run --rm -e MYSQL_ROOT_PASSWORD=test -p 3306:3306 mysql:8
    MongoDB:   docker run --rm -p 27017:27017 mongo:7
    Kafka:     (needs docker-compose, covered in concept file 03)

  Zero installation. Exact version control. Disposable.
""")


# ============================================================
# QUICK REFERENCE
# ============================================================

print()
print("=" * 70)
print("  QUICK REFERENCE — Docker Commands from this file")
print("=" * 70)
print("""
  IMAGES:
    docker pull image:tag              download image from registry
    docker images                      list local images
    docker rmi image:tag               remove local image
    docker image history image:tag     see image layers
    docker image prune                 remove all unused images

  RUN CONTAINERS:
    docker run image:tag CMD           run command, exit, keep container
    docker run --rm image:tag CMD      run command, exit, auto-remove
    docker run -it image:tag bash      interactive shell
    docker run -d --name NAME image    run in background with name
    docker run -p 5432:5432 image      map port (host:container)
    docker run -v ./data:/app/data img mount local directory
    docker run -e KEY=VALUE image      set environment variable
    docker run --env-file .env image   load env vars from file

  MANAGE CONTAINERS:
    docker ps                          list running containers
    docker ps -a                       list all containers (incl. stopped)
    docker logs container_name         view stdout/stderr
    docker logs -f container_name      follow logs live
    docker exec -it container bash     shell into running container
    docker stop container_name         graceful stop
    docker rm container_name           remove stopped container
    docker rm -f container_name        force stop + remove
    docker container prune             remove all stopped containers

  DATA ENGINEER SHORTCUTS:
    # Throwaway Postgres
    docker run --rm -e POSTGRES_PASSWORD=test -p 5432:5432 postgres:15

    # Connect to running Postgres container
    docker exec -it dev_postgres psql -U postgres

    # See live logs from your pipeline
    docker logs -f my_pipeline

    # Shell into a running pipeline container to debug
    docker exec -it my_pipeline bash
""")
