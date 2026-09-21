"""
Week 3 Practice Exercises — Docker for Data Pipelines
======================================================
These exercises are designed to be worked through WITH Docker installed.
If you don't have Docker yet, read through the exercises and solutions —
the mental model is the important part.

SETUP:
  1. Install Docker Desktop: https://docs.docker.com/get-docker/
  2. Verify Docker is running: docker info
  3. Run the setup function to print instructions:
       python3 exercises.py setup

  Most exercises involve writing files and running docker commands.
  Where Docker isn't available, conceptual answers are accepted.

HOW TO USE:
  1. Read the scenario and tasks
  2. Attempt the answer yourself (write the file, run the command)
  3. Check the SOLUTION to compare
  4. For file exercises: actually create the files and test them

  python3 exercises.py           — print all exercises + solutions
  python3 exercises.py setup     — print setup instructions
"""

import sys
import os


# ============================================================
# SETUP
# ============================================================

def setup():
    """Print setup instructions and verify Docker."""
    print("=" * 70)
    print("  WEEK 3 SETUP — Docker Exercises")
    print("=" * 70)
    print("""
  Prerequisites:
    1. Docker Desktop installed and running
       Download: https://docs.docker.com/get-docker/
       macOS:    brew install --cask docker
       Ubuntu:   follow docs.docker.com/engine/install/ubuntu/

  Verify setup:
    docker info           — should print Docker version info
    docker ps             — should show an empty table (no containers yet)
    docker pull python:3.11-slim   — download the image we'll use

  Create practice directory:
    mkdir -p ~/docker_practice && cd ~/docker_practice

  For file-based exercises, create the files in ~/docker_practice/.

  Most exercises print commands to run. Actually RUN them.
  Reading about Docker is 10% of learning it. Running commands is 90%.
""")

    # Try to verify Docker is available
    result = os.popen("docker info 2>/dev/null | head -3").read().strip()
    if result:
        print("  Docker status: RUNNING")
        print(f"  {result.splitlines()[0]}")
    else:
        print("  Docker status: NOT RUNNING (start Docker Desktop)")

    print()
    print("  Run exercises: python3 exercises.py")


# ============================================================
# EXERCISE 1 — Image Exploration
# ============================================================

EXERCISE_1 = """
EXERCISE 1 — Image Exploration
================================
Goal: Get comfortable pulling images and understanding what's inside them.

Tasks:
  a) Pull these two images:
       docker pull postgres:15
       docker pull python:3.11-slim

  b) After pulling, list all local images and note their sizes.
     Which is bigger? By how much?

  c) Run python:3.11-slim interactively and explore it:
       docker run -it --rm python:3.11-slim bash
     Inside the container, run:
       - python3 --version
       - pip list         (what packages are pre-installed?)
       - ls /             (what does the Linux filesystem look like?)
       - cat /etc/os-release  (what Linux distro is this?)
       - which python3    (where is python installed?)
     Type 'exit' when done.

  d) Run postgres:15 interactively:
       docker run --rm -e POSTGRES_PASSWORD=test postgres:15 postgres --version
     This should print the Postgres version and exit.

  e) Conceptual question:
     Why is python:3.11-slim much smaller than postgres:15?
     What does the 'slim' tag actually remove?

HINT: docker pull, docker images, docker run -it --rm
"""

SOLUTION_1 = """
SOLUTION 1:

  a) Pull images:
     docker pull postgres:15
     docker pull python:3.11-slim

  b) List and compare sizes:
     docker images

     Expected sizes (approx):
       python:3.11-slim   ~130MB   (Debian base + Python only)
       postgres:15        ~379MB   (Debian + Python + Postgres + extensions)

     Postgres is ~3x bigger because it includes:
       - PostgreSQL server and client binaries
       - Multiple language extensions (plpgsql, etc.)
       - Development headers and libraries
       - SSL libraries (libssl)

  c) Exploring python:3.11-slim:
     docker run -it --rm python:3.11-slim bash

     python3 --version       → Python 3.11.x
     pip list                → pip, setuptools, wheel (almost nothing else)
     ls /                    → standard Linux: bin, etc, lib, usr, var...
     cat /etc/os-release     → Debian GNU/Linux 12 (bookworm)
     which python3           → /usr/local/bin/python3

  d) Postgres version:
     docker run --rm -e POSTGRES_PASSWORD=test postgres:15 postgres --version
     Output: postgres (PostgreSQL) 15.x

  e) What 'slim' removes:
     'slim' removes:
       - Build tools (gcc, g++, make) — needed to compile packages from source
       - Documentation (man pages)
       - Locales except C and POSIX (reduces size by ~20MB)
       - Some system utilities not needed at runtime

     'slim' KEEPS:
       - Python interpreter
       - pip
       - Core system libraries (glibc, libssl, etc.)
       - Everything needed to INSTALL and RUN pure-Python packages

     Binary wheels (pandas, numpy, psycopg2-binary) work fine on slim.
     Packages that need compilation from source may fail without build tools.
"""


# ============================================================
# EXERCISE 2 — Dockerfile Writing
# ============================================================

EXERCISE_2 = """
EXERCISE 2 — Write a Dockerfile and Fix Layer Caching
=======================================================
Goal: Write a Dockerfile, identify caching mistakes, fix them.

Setup:
  Create a directory: mkdir -p ~/docker_practice/etl_app
  Create these files:

  requirements.txt:
    pandas==2.1.0
    sqlalchemy==2.0.23
    psycopg2-binary==2.9.9

  pipeline.py:
    import pandas as pd
    import sqlalchemy
    print(f"pandas: {pd.__version__}")
    print(f"sqlalchemy: {sqlalchemy.__version__}")
    print("Pipeline ready!")

Tasks:
  a) Write a Dockerfile that:
       - Uses python:3.11-slim as base
       - Sets WORKDIR /app
       - Copies requirements.txt and installs packages
       - Copies the rest of the code
       - Sets PYTHONUNBUFFERED=1
       - Default command: python pipeline.py

  b) Build it: docker build -t etl_app:v1 .
     Run it:   docker run --rm etl_app:v1
     Expected output: prints pandas and sqlalchemy versions, "Pipeline ready!"

  c) Spot the caching BUG in this WRONG Dockerfile:
       FROM python:3.11-slim
       WORKDIR /app
       COPY . .
       RUN pip install --no-cache-dir -r requirements.txt
       ENV PYTHONUNBUFFERED=1
       CMD ["python", "pipeline.py"]

     What is the cache problem? What rebuild does a code change trigger?

  d) Fix the wrong Dockerfile. Show the corrected version.
     Then demonstrate the fix: modify pipeline.py (add any print),
     rebuild, and note which layers are cached vs rebuilt.

  e) Write a .dockerignore for this project.
     What files/folders should definitely be excluded?

HINT: COPY requirements.txt . before RUN pip install
"""

SOLUTION_2 = """
SOLUTION 2:

  a) Correct Dockerfile:

     FROM python:3.11-slim

     WORKDIR /app

     COPY requirements.txt .
     RUN pip install --no-cache-dir -r requirements.txt

     COPY . .

     ENV PYTHONUNBUFFERED=1

     CMD ["python", "pipeline.py"]

  b) Build and run:
     docker build -t etl_app:v1 .
     docker run --rm etl_app:v1
     # Output:
     # pandas: 2.1.0
     # sqlalchemy: 2.0.23
     # Pipeline ready!

  c) The WRONG Dockerfile cache problem:
     Line 3: COPY . .   ← copies ALL files including pipeline.py

     When you change pipeline.py:
       COPY . .    → CACHE MISS (pipeline.py changed)
       pip install → REBUILDS   (previous layer changed)

     Every code change triggers a full pip install (3-5 minutes).
     This happens because 'pip install' comes AFTER 'COPY . .',
     so any code change invalidates the pip install layer.

  d) Fixed Dockerfile (same as part a):
     The fix is: COPY requirements.txt . BEFORE COPY . .

     After the fix, modifying pipeline.py:
       FROM python:3.11-slim         [CACHED]
       WORKDIR /app                  [CACHED]
       COPY requirements.txt .       [CACHED]  ← requirements.txt unchanged
       RUN pip install               [CACHED]  ← previous layer unchanged!
       COPY . .                      [CACHE MISS]  ← pipeline.py changed
       ENV PYTHONUNBUFFERED=1        [rebuilds]
       CMD                           [rebuilds]

     Result: 2-second rebuild instead of 5-minute rebuild.

  e) .dockerignore:
     .git/
     .venv/
     venv/
     __pycache__/
     *.pyc
     .env
     data/
     *.csv
     *.parquet
     .DS_Store
     tests/
"""


# ============================================================
# EXERCISE 3 — docker-compose Stack
# ============================================================

EXERCISE_3 = """
EXERCISE 3 — Write a docker-compose Stack
==========================================
Goal: Write a docker-compose.yml for a pipeline + Postgres stack.

Tasks:
  a) Write a docker-compose.yml that defines:
       - A 'postgres' service using postgres:15
         * Env vars: POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB from .env
         * Named volume: postgres_data
         * Healthcheck: pg_isready command
         * Port: 5432:5432
       - A 'pipeline' service built from a local Dockerfile
         * env_file: .env
         * depends_on postgres with condition: service_healthy
         * Both on a custom network: pipeline_net
       - Named volume: postgres_data
       - Custom network: pipeline_net

  b) Write the .env.example file for this stack.
     Include all variables the postgres service needs.

  c) What command do you run to:
       - Start everything in the background?
       - Watch the pipeline logs live?
       - Connect to Postgres with psql inside the container?
       - Stop everything but keep the data?
       - Delete everything including the data?

  d) The pipeline's Python code uses:
       DB_HOST = os.environ.get("DB_HOST", "localhost")
     What value must DB_HOST be in the .env file for this to work
     inside docker-compose? Why?

  e) What does depends_on: condition: service_healthy do differently
     than depends_on: [postgres] (no condition)?

HINT: pg_isready, service_healthy, postgres as hostname
"""

SOLUTION_3 = """
SOLUTION 3:

  a) docker-compose.yml:

     services:
       postgres:
         image: postgres:15
         environment:
           POSTGRES_USER: ${DB_USER}
           POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
           POSTGRES_DB: ${DB_NAME}
         ports:
           - "5432:5432"
         volumes:
           - postgres_data:/var/lib/postgresql/data
         networks:
           - pipeline_net
         healthcheck:
           test: ["CMD-SHELL", "pg_isready -U ${DB_USER} -d ${DB_NAME}"]
           interval: 5s
           timeout: 5s
           retries: 5
           start_period: 10s

       pipeline:
         build: .
         env_file:
           - .env
         depends_on:
           postgres:
             condition: service_healthy
         networks:
           - pipeline_net

     volumes:
       postgres_data:

     networks:
       pipeline_net:

  b) .env.example:
     DB_USER=pipeline_user
     DB_NAME=pipeline_db
     DB_HOST=postgres
     DB_PORT=5432
     DB_PASSWORD=your_password_here
     POSTGRES_PASSWORD=your_password_here

  c) Commands:
     Start all:         docker-compose up -d
     Watch logs:        docker-compose logs -f pipeline
     Connect to psql:   docker-compose exec postgres psql -U pipeline_user -d pipeline_db
     Stop keep data:    docker-compose down
     Delete everything: docker-compose down -v

  d) DB_HOST must be "postgres" (the service name in docker-compose.yml).
     Reason: inside the Docker network, each service is reachable by
     its SERVICE NAME, not "localhost". "localhost" inside the pipeline
     container refers to the pipeline container itself.
     Docker Compose creates an internal DNS where "postgres" resolves
     to the postgres container's IP address.

  e) depends_on: [postgres]  (no condition):
       Waits for the postgres CONTAINER to START.
       Container starts in ~1 second. But PostgreSQL inside it takes 3-10s.
       Pipeline starts, tries to connect → "connection refused" → crashes.

     depends_on: condition: service_healthy:
       Waits for the healthcheck (pg_isready) to PASS.
       pg_isready returns success only when Postgres accepts connections.
       Pipeline doesn't start until Postgres is actually ready.
       No connection-refused errors. Reliable startup.
"""


# ============================================================
# EXERCISE 4 — Debug a Crashing Container
# ============================================================

EXERCISE_4 = """
EXERCISE 4 — Debug a Container That Exits Immediately
======================================================
Goal: Learn the systematic approach to debugging containers.

Scenario:
  You run: docker-compose up -d
  You check: docker-compose ps
  You see: pipeline service shows "Exit 1" instead of "Up"
  The container started and immediately stopped.

Tasks:
  a) What is the FIRST command you run to diagnose this?
     What are you looking for?

  b) List 5 common reasons a Python container exits immediately.
     For each, describe what the error would look like in the logs.

  c) You see this in the logs:
       ModuleNotFoundError: No module named 'pandas'
     What caused this? What are two ways to fix it?

  d) You see this in the logs:
       psycopg2.OperationalError: could not connect to server: Connection refused
     The postgres service shows "Up (healthy)".
     What is the likely cause? What is the fix?

  e) You see this in the logs:
       FileNotFoundError: [Errno 2] No such file or directory: '/app/config.yml'
     The file exists on your machine in ./config.yml.
     What is the most likely cause? How do you fix it?

  f) Your container is running but the pipeline is slow.
     It's supposed to take 30 seconds but takes 5 minutes.
     What command shows you live resource usage?
     What might be the issue?

HINT: docker-compose logs, docker stats, COPY instruction, .dockerignore
"""

SOLUTION_4 = """
SOLUTION 4:

  a) First command: docker-compose logs pipeline
     (or: docker-compose logs --tail=50 pipeline)

     Looking for:
       - The last error message before exit
       - The Python traceback (if a Python exception caused the crash)
       - Any "Error" or "Exception" lines
       - Import errors (missing packages)
       - Connection errors (can't reach database)
       - File not found errors

  b) 5 common crash reasons:

     1. Import error — missing package:
          ModuleNotFoundError: No module named 'pandas'
        Package not in requirements.txt or requirements.txt not copied/installed.

     2. Connection error — DB not ready or wrong host:
          psycopg2.OperationalError: could not connect to server: Connection refused
        Pipeline started before Postgres was ready (missing healthcheck).
        Or DB_HOST="localhost" instead of the service name.

     3. Missing file — code references a file that wasn't copied:
          FileNotFoundError: [Errno 2] No such file or directory: '/app/config.yml'
        File in .dockerignore, or COPY instruction didn't include it.

     4. Syntax error in Python code:
          SyntaxError: invalid syntax (pipeline.py, line 42)
        Code has a bug. Easy to miss if you didn't test locally first.

     5. Missing environment variable — code calls os.environ[KEY] (not .get):
          KeyError: 'DB_PASSWORD'
        The .env file isn't loaded, or the variable name is wrong.
        Fix: use os.environ.get('DB_PASSWORD') with a default, or fix .env.

  c) ModuleNotFoundError: No module named 'pandas'
     Cause:
       - 'pandas' not in requirements.txt
       - OR requirements.txt wasn't copied into the image before pip install
       - OR requirements.txt was in .dockerignore (unlikely but possible)
       - OR the image was cached before requirements.txt was updated

     Two fixes:
       Fix 1: Add pandas to requirements.txt, rebuild:
                docker-compose up -d --build pipeline
       Fix 2: Force rebuild ignoring cache:
                docker-compose build --no-cache pipeline
                docker-compose up -d

  d) psycopg2 connection refused despite postgres being healthy:
     Likely cause: DB_HOST="localhost" in .env instead of DB_HOST="postgres"

     The pipeline container cannot reach Postgres on "localhost"
     because "localhost" resolves to the pipeline container itself.
     The service must be reached by its service name: "postgres".

     Fix: in .env, change DB_HOST=localhost to DB_HOST=postgres

  e) FileNotFoundError: config.yml not found:
     Most likely cause: config.yml is in .dockerignore

     Check: is config.yml (or a matching pattern) in .dockerignore?
     For example: *.yml in .dockerignore would exclude it.

     Fix 1: Remove config.yml from .dockerignore, rebuild.
     Fix 2: Use a bind mount for config: -v ./config.yml:/app/config.yml
     Fix 3: Pass config values as environment variables instead.

  f) Slow container debugging:
     Command: docker stats
     Shows real-time CPU and memory for all containers.

     Possible causes:
       - Memory limit too low: container swapping to disk (look for high MEM%)
       - CPU limit too low: constrained to 0.25 CPUs (look for high CPU%)
       - pandas trying to load a file that's larger than available RAM
       - No memory limit: pipeline is consuming all host RAM, slowing everything

     Fix: increase resource limits or optimize the pipeline code.
"""


# ============================================================
# EXERCISE 5 — Size Optimization
# ============================================================

EXERCISE_5 = """
EXERCISE 5 — Reduce a Bloated Image
=====================================
Goal: Apply the size optimization techniques to a badly written Dockerfile.

Here is a bloated Dockerfile:

  FROM python:3.11
  COPY . .
  RUN pip install pandas sqlalchemy psycopg2-binary requests boto3
  WORKDIR /app
  ENV DB_PASSWORD=mypassword123
  CMD ["python", "pipeline.py"]

Tasks:
  a) List EVERY problem in this Dockerfile.
     For each problem, explain what it costs (size, security, speed, etc.)

  b) Rewrite the Dockerfile correctly, fixing all problems.

  c) Estimate the size difference between the original and fixed:
     - python:3.11 base image: ~900MB
     - python:3.11-slim base:  ~130MB
     - pandas + sqlalchemy + psycopg2-binary + requests + boto3: ~200MB
     - pip cache (without --no-cache-dir): ~50MB

     What's the final estimated size of the WRONG Dockerfile?
     What's the estimated size of the FIXED Dockerfile?

  d) Why is WORKDIR defined AFTER COPY in the wrong version problematic?
     What directory do the files end up in?

  e) If you already built the wrong image with the password in it,
     and pushed it to Docker Hub by mistake — what do you do?
     (Removing the image isn't enough — why not?)

HINT: FROM python:3.11-slim, no --no-cache-dir, ENV with secrets, layer order
"""

SOLUTION_5 = """
SOLUTION 5:

  a) Problems in the bloated Dockerfile:

     1. FROM python:3.11  (should be python:3.11-slim)
        Cost: ~900MB base instead of ~130MB = +770MB for nothing.

     2. COPY . . before WORKDIR
        Cost: files are copied to / (root) not /app. Confusing paths.
        Also: COPY . . comes before pip install (layer cache problem).

     3. pip install without --no-cache-dir
        Cost: pip stores downloaded .whl files in /root/.cache/pip
        This adds 50-100MB to the image for no benefit at runtime.

     4. COPY . . before pip install (layer order problem)
        Cost: any code change → full pip reinstall (slow rebuilds).

     5. WORKDIR /app defined AFTER COPY . .
        Cost: COPY . . runs before WORKDIR exists/is set,
        so files land in / (the filesystem root). Messy.

     6. ENV DB_PASSWORD=mypassword123
        SECURITY ISSUE: password is baked into the image permanently.
        Visible in docker history. If pushed to a registry, it's exposed.
        Can never be "removed" without building a completely new image.

  b) Fixed Dockerfile:

     FROM python:3.11-slim

     WORKDIR /app

     COPY requirements.txt .
     RUN pip install --no-cache-dir pandas sqlalchemy psycopg2-binary requests boto3

     COPY . .

     ENV PYTHONUNBUFFERED=1

     CMD ["python", "pipeline.py"]
     # DB_PASSWORD passed at runtime: docker run --env-file .env my_pipeline

  c) Size estimates:

     WRONG Dockerfile:
       python:3.11 base:           ~900MB
       pip install (5 packages):   ~200MB
       pip cache (no --no-cache):  ~80MB
       COPY . .:                   ~5MB
       Total estimated:            ~1185MB (~1.2GB)

     FIXED Dockerfile:
       python:3.11-slim base:      ~130MB
       pip install --no-cache-dir: ~200MB
       COPY . .:                   ~5MB
       Total estimated:            ~335MB

     Savings: ~850MB — over 70% smaller image.

  d) WORKDIR after COPY:
     When COPY . . runs, there is no WORKDIR set, so files go to /
     (the filesystem root). The WORKDIR /app instruction later creates
     /app as the working directory, but the files aren't there.
     CMD ["python", "pipeline.py"] runs from /app, but pipeline.py
     is in / — so it fails with "python: can't open file 'pipeline.py'".

  e) If you accidentally pushed an image with a secret:
     The password is baked into an image layer. Even if you delete the image
     from Docker Hub, old cached versions may exist locally on machines
     that already pulled it.

     Removing the image from Docker Hub removes the public copy,
     but anyone who already pulled it has the password in their local cache.
     'docker image history' on their local copy still shows it.

     Correct response:
       1. ROTATE THE CREDENTIAL IMMEDIATELY — change the DB password NOW.
          The password in the image is useless once the credential is changed.
       2. Delete the image from Docker Hub / ECR.
       3. Tell all team members to 'docker rmi' the compromised image.
       4. Audit: who might have seen/used the password?
       5. Fix the Dockerfile to never put secrets in ENV again.

     Moral: rotate first, clean up second. The image is the symptom.
     The exposed credential is the actual problem.
"""


# ============================================================
# EXERCISE 6 — Networking Diagnosis
# ============================================================

EXERCISE_6 = """
EXERCISE 6 — Fix Docker Compose Networking
============================================
Goal: Diagnose and fix the "can't connect to database" problem.

Scenario A:
  Your pipeline.py has:
    DB_HOST = os.environ.get("DB_HOST", "localhost")
  Your .env has:
    DB_HOST=localhost
  You run docker-compose up -d.
  The pipeline crashes with: "connection refused to localhost:5432"

  a) Explain exactly why this fails.
  b) What is the one-line fix?

Scenario B:
  Both services are running. You confirm postgres is healthy.
  You change .env: DB_HOST=postgres
  You run: docker-compose up -d
  The pipeline still crashes with "connection refused to localhost:5432"
  (Note: still says localhost even though you changed it to postgres!)

  c) Why does the pipeline still use "localhost"?
     What did you forget to do?
  d) What is the correct sequence of commands to pick up the .env change?

Scenario C:
  You want to connect to Postgres from your laptop (from outside Docker)
  using DBeaver or TablePlus. You try:
    Host: postgres
    Port: 5432
  It fails.

  e) Why does "postgres" not work from your laptop?
     What host should you use from outside Docker?
  f) What must be configured in docker-compose.yml for this to work?

HINT: container name vs service name, localhost vs service name, port mapping
"""

SOLUTION_6 = """
SOLUTION 6:

  a) Why localhost fails in docker-compose:
     Inside the pipeline container, "localhost" refers to the PIPELINE
     CONTAINER's own network interface (127.0.0.1 of the pipeline container).
     There is no Postgres listening on the pipeline container's localhost.
     Postgres is running in a DIFFERENT container with its own isolated network.

     Docker Compose creates an internal DNS for the custom network.
     The postgres container is reachable by its SERVICE NAME "postgres",
     not by "localhost".

  b) One-line fix in .env:
     DB_HOST=postgres
     (Change "localhost" to "postgres" — the service name in docker-compose.yml)

  c) Why the pipeline still uses localhost after changing .env:
     The pipeline container was NOT restarted after changing .env.
     docker-compose up -d with no --build only starts containers that aren't
     already running. The pipeline container already exists (even if "exited")
     with the OLD environment variables baked in at creation time.

  d) Correct sequence to pick up .env changes:
     docker-compose down         # remove old containers (clears old env)
     docker-compose up -d        # create new containers with updated .env

     OR:
     docker-compose up -d --force-recreate pipeline  # recreate just pipeline

     NOT: docker-compose restart pipeline
     (restart uses the existing container — doesn't reload .env)

  e) Why "postgres" doesn't work from your laptop:
     "postgres" is a hostname that only exists inside the Docker network.
     Docker's internal DNS resolves "postgres" → postgres container IP,
     but only for containers ON that network.
     Your laptop is NOT on the Docker network — its DNS doesn't know
     what "postgres" means.

     From your laptop, use: localhost (or 127.0.0.1)

  f) Port mapping required in docker-compose.yml:
     The postgres service must have:
       ports:
         - "5432:5432"   # host_port:container_port

     This forwards localhost:5432 on your machine to port 5432 inside
     the postgres container. Without this, Postgres is only accessible
     from within the Docker network.

     Connection settings from your laptop:
       Host: localhost (or 127.0.0.1)
       Port: 5432
       User: pipeline_user (from .env)
       Password: (from .env)
       Database: pipeline_db (from .env)
"""


# ============================================================
# EXERCISE 7 — Secrets Audit
# ============================================================

EXERCISE_7 = """
EXERCISE 7 — Secrets Audit: Find and Fix All the Problems
===========================================================
Goal: Identify every secrets mistake and know how to fix each one.

Here is a real-looking (and intentionally broken) set of files.
Find ALL the security problems.

File 1 — Dockerfile:
  FROM python:3.11-slim
  WORKDIR /app
  ENV DB_HOST=prod-db.internal
  ENV DB_USER=pipeline_user
  ENV DB_PASSWORD=Pg@ssw0rd_2024!
  ENV AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
  ENV AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
  COPY requirements.txt .
  RUN pip install --no-cache-dir -r requirements.txt
  COPY . .
  CMD ["python", "pipeline.py"]

File 2 — docker-compose.yml:
  services:
    postgres:
      image: postgres:15
      environment:
        POSTGRES_USER: pipeline_user
        POSTGRES_PASSWORD: Pg@ssw0rd_2024!
        POSTGRES_DB: pipeline_db
    pipeline:
      build: .
      environment:
        DB_HOST: postgres
        DB_PASSWORD: Pg@ssw0rd_2024!
        AWS_ACCESS_KEY_ID: AKIAIOSFODNN7EXAMPLE
        AWS_SECRET_ACCESS_KEY: wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY

File 3 — .gitignore:
  __pycache__/
  *.pyc
  .venv/

Tasks:
  a) List every secret/credential problem in each file.
     How many total problems are there?

  b) Rewrite all three files correctly (Dockerfile, docker-compose.yml, .gitignore).

  c) Write the .env.example file that would replace the hardcoded values.

  d) How would you check if secrets were already committed to git?
     What command reveals secrets in git history?

  e) If these files were already committed and pushed to GitHub,
     what are the two mandatory steps (in order)?

HINT: .env, .gitignore, ENV in Dockerfile, hardcoded in compose, git log -p
"""

SOLUTION_7 = """
SOLUTION 7:

  a) Problems found (7 total):

     Dockerfile — 4 problems:
       1. ENV DB_PASSWORD=Pg@ssw0rd_2024!     — DB password in image layer
       2. ENV AWS_ACCESS_KEY_ID=AKIA...       — AWS key ID in image layer
       3. ENV AWS_SECRET_ACCESS_KEY=wJal...   — AWS secret in image layer
          (ANY secret in Dockerfile ENV is baked into image history permanently)
       4. ENV DB_HOST and DB_USER are hardcoded — not secrets but inflexible

     docker-compose.yml — 2 problems:
       5. POSTGRES_PASSWORD: Pg@ss...  — if compose file is in git, password is too
       6. AWS keys hardcoded in environment: — same issue

     .gitignore — 1 problem:
       7. .env is NOT in .gitignore — if someone creates a .env with real
          values, git will happily commit it

  b) Fixed files:

     Dockerfile (clean — no secrets):
       FROM python:3.11-slim
       WORKDIR /app
       COPY requirements.txt .
       RUN pip install --no-cache-dir -r requirements.txt
       COPY . .
       ENV PYTHONUNBUFFERED=1
       CMD ["python", "pipeline.py"]
       # ALL secrets passed at runtime via --env-file .env

     docker-compose.yml (clean):
       services:
         postgres:
           image: postgres:15
           environment:
             POSTGRES_USER: ${DB_USER}
             POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
             POSTGRES_DB: ${DB_NAME}
         pipeline:
           build: .
           env_file:
             - .env
           depends_on:
             postgres:
               condition: service_healthy

     .gitignore (fixed):
       __pycache__/
       *.pyc
       .venv/
       .env           ← ADDED
       .env.local     ← ADDED
       .env.*.local   ← ADDED

  c) .env.example (commit this):
     DB_HOST=postgres
     DB_USER=pipeline_user
     DB_NAME=pipeline_db
     DB_PORT=5432
     DB_PASSWORD=your_db_password_here
     POSTGRES_PASSWORD=your_db_password_here
     AWS_ACCESS_KEY_ID=your_aws_key_id_here
     AWS_SECRET_ACCESS_KEY=your_aws_secret_here

  d) Check if secrets were committed:
     git log -p --all -S "password"     — search history for "password"
     git log -p --all -S "AKIA"         — search for AWS key patterns
     git grep -n "password" HEAD        — search current HEAD
     git log --oneline --all            — see all commits

     Third-party scanners:
       git-secrets (AWS Labs)
       truffleHog
       gitleaks

  e) If already committed and pushed — mandatory steps IN THIS ORDER:

     1. ROTATE ALL EXPOSED CREDENTIALS IMMEDIATELY
        - Change the DB password right now
        - Invalidate / delete the AWS access key and create a new one
        - Assume they are compromised — someone may already be using them
        - Check AWS CloudTrail for unexpected API calls in last 24h

     2. Remove from repository history (optional / best-effort)
        git filter-branch or git-filter-repo can rewrite history,
        but anyone who cloned the repo before still has the secrets.
        GitHub also requires opening a support ticket to purge cached views.

        git-filter-repo --invert-paths --path Dockerfile (rewrites all history)
        Force push all branches (coordination with team required)
        All team members must re-clone (their local history has the secrets)

     The credential rotation is mandatory and urgent.
     The history cleanup is important but secondary — the leaked credential
     is the actual security risk, not the history entry.
"""


# ============================================================
# MAIN
# ============================================================

def print_exercises():
    exercises = [
        ("Exercise 1", EXERCISE_1, SOLUTION_1),
        ("Exercise 2", EXERCISE_2, SOLUTION_2),
        ("Exercise 3", EXERCISE_3, SOLUTION_3),
        ("Exercise 4", EXERCISE_4, SOLUTION_4),
        ("Exercise 5", EXERCISE_5, SOLUTION_5),
        ("Exercise 6", EXERCISE_6, SOLUTION_6),
        ("Exercise 7", EXERCISE_7, SOLUTION_7),
    ]

    print("=" * 70)
    print("  WEEK 3 PRACTICE EXERCISES — Docker for Data Pipelines")
    print("=" * 70)
    print("""
  Each exercise has a real scenario you'll face as a data engineer.
  Try the tasks yourself BEFORE reading the solution.

  Exercises 1-2: Requires Docker to be running.
  Exercises 3-7: Conceptual — answer before reading solution.
""")

    for name, exercise, solution in exercises:
        print(exercise)
        print("-" * 50)
        print("  (Try it yourself, then scroll for solution)")
        print()
        print(solution)
        print()
        print("=" * 70)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "setup":
        setup()
    else:
        print_exercises()
