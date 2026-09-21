"""
Docker for Data Engineers — Writing Dockerfiles for Python Apps
===============================================================
An image doesn't appear from nowhere.
You describe how to build it in a Dockerfile — a text file with
a recipe of instructions. Docker reads the recipe and bakes the image.

This file covers:
- Dockerfile anatomy: every instruction explained
- Layer caching: the single most important optimization concept
- Base image choices and size trade-offs
- .dockerignore: what to exclude from your image
- Multi-stage builds: keeping production images lean
- Security best practices for data pipeline images
- A complete, production-quality Dockerfile example

Run this file: python3 02_dockerfile_for_python_data_apps.py
Dockerfiles are shown as text with line-by-line explanations.
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
    """Print a Docker command with explanation."""
    print(f"\n  $ {cmd}")
    if note:
        print(f"  # {note}")
    if explanation:
        for line in explanation.strip().splitlines():
            print(f"    {line}")


def show_file(filename, content, explanation=""):
    """Display a file's contents with annotations."""
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
# 1. WHAT IS A DOCKERFILE?
# ============================================================

section("1. WHAT IS A DOCKERFILE?")

print("""
  A Dockerfile is a plain text file named exactly 'Dockerfile' (no extension).
  It contains ordered instructions that Docker executes top-to-bottom
  to build your image.

  The build process:
    1. You write a Dockerfile
    2. You run 'docker build -t my_pipeline:1.0 .'
       (the '.' tells Docker where to find the Dockerfile and source files)
    3. Docker executes each instruction and creates a new layer
    4. Result: a reusable image tagged 'my_pipeline:1.0'
    5. You run 'docker run my_pipeline:1.0' to create a container

  Dockerfile → [docker build] → Image → [docker run] → Container
""")


# ============================================================
# 2. DOCKERFILE ANATOMY — LINE BY LINE
# ============================================================

section("2. DOCKERFILE ANATOMY — Every Instruction Explained")

BASIC_DOCKERFILE = """
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1

CMD ["python", "pipeline.py"]
"""

show_file("Dockerfile", BASIC_DOCKERFILE)

print("""
  LINE BY LINE:

  FROM python:3.11-slim
  ─────────────────────
  Every Dockerfile starts with FROM. It specifies the BASE IMAGE —
  the starting point you're building on top of.
  'python:3.11-slim' = Python 3.11 on Debian Bookworm (slim variant).
  This gives you: Linux OS + Python 3.11 + pip, nothing else.

  You NEVER build from scratch. You always start from an existing image.
  FROM is always the first instruction.


  WORKDIR /app
  ────────────
  Sets the working directory for all subsequent instructions.
  Like 'cd /app' that persists throughout the build AND at runtime.
  If /app doesn't exist, Docker creates it.
  Best practice: always set a WORKDIR. Without it, you're in /
  and file paths become unpredictable.


  COPY requirements.txt .
  ───────────────────────
  COPY <source-on-your-machine> <destination-in-container>
  The '.' destination means: copy into the current WORKDIR (/app).
  This copies just requirements.txt BEFORE pip install.
  Why? Layer caching. (Explained in detail in section 3.)


  RUN pip install --no-cache-dir -r requirements.txt
  ──────────────────────────────────────────────────
  RUN executes a shell command during the BUILD phase.
  --no-cache-dir: don't store pip's download cache in the image.
    Without this flag: pip stores .whl files inside the image layer,
    inflating the image size by 50-200MB for nothing.
  This layer is CACHED until requirements.txt changes.
  Changing pipeline.py doesn't invalidate this layer.


  COPY . .
  ────────
  Copy ALL remaining files from your machine into the container's WORKDIR.
  Source: everything in the build context (filtered by .dockerignore).
  Destination: /app (current WORKDIR).
  This happens AFTER pip install — so changing code doesn't trigger
  a full reinstall of packages. (The big win of layer caching.)


  ENV PYTHONUNBUFFERED=1
  ──────────────────────
  Set an environment variable inside the image.
  PYTHONUNBUFFERED=1 forces Python to write output immediately to stdout.
  Without it: Python buffers output, so 'print("Processing...")' might
  not appear in 'docker logs' until Python flushes the buffer (or exits).
  For data pipelines that log progress, this is essential.
  Also set via: python -u pipeline.py (but ENV is cleaner)


  CMD ["python", "pipeline.py"]
  ─────────────────────────────
  The default command to run when a container starts.
  Uses JSON array format (exec form) — no shell interpretation.
  'docker run my_pipeline:1.0' → runs 'python pipeline.py'
  'docker run my_pipeline:1.0 python other.py' → overrides CMD

  CMD vs ENTRYPOINT:
    CMD:        can be overridden by 'docker run image OVERRIDE'
    ENTRYPOINT: can't be overridden (use for always-run commands)
    In practice: use CMD for data pipelines (flexibility is useful)
""")


# ============================================================
# 3. LAYER CACHING — THE MOST IMPORTANT OPTIMIZATION
# ============================================================

section("3. LAYER CACHING — The Difference Between 2 Seconds and 5 Minutes")

print("""
  Docker caches each layer. On rebuild, it reuses cached layers
  until it finds a change, then rebuilds from that point forward.

  WRONG ORDER — every code change reinstalls ALL packages:
""")

WRONG_DOCKERFILE = """
FROM python:3.11-slim
WORKDIR /app
COPY . .                               # <-- copies everything, including pipeline.py
RUN pip install --no-cache-dir -r requirements.txt
CMD ["python", "pipeline.py"]
"""

show_file("Dockerfile (WRONG)", WRONG_DOCKERFILE)

print("""
  What happens when you change one line in pipeline.py:

    Layer 1: FROM python:3.11-slim         [CACHED]   ~0s
    Layer 2: WORKDIR /app                  [CACHED]   ~0s
    Layer 3: COPY . .   ← pipeline.py changed!  [CACHE MISS] ~1s
    Layer 4: pip install (50+ packages)    [REBUILDS]  3-5 minutes
    Layer 5: CMD                           [REBUILDS]  ~0s

  Every single code change = 5 minute rebuild. Unbearable.
""")

print("""
  RIGHT ORDER — dependencies cached separately from code:
""")

RIGHT_DOCKERFILE = """
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .                # <-- only requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY . .                               # <-- code copied AFTER pip install
CMD ["python", "pipeline.py"]
"""

show_file("Dockerfile (RIGHT)", RIGHT_DOCKERFILE)

print("""
  What happens when you change one line in pipeline.py:

    Layer 1: FROM python:3.11-slim         [CACHED]   ~0s
    Layer 2: WORKDIR /app                  [CACHED]   ~0s
    Layer 3: COPY requirements.txt .       [CACHED]   ~0s  ← unchanged
    Layer 4: pip install                   [CACHED]   ~0s  ← unchanged!
    Layer 5: COPY . .   ← pipeline.py changed!  [CACHE MISS] ~1s
    Layer 6: CMD                           [REBUILDS]  ~0s

  Code change = 2 second rebuild. 150x faster.

  VISUAL SUMMARY:

  Change type:             Code only    Code + new dep
  ─────────────────────────────────────────────────────
  WRONG Dockerfile:         5 min          5 min
  RIGHT Dockerfile:         2 sec          5 min
  ─────────────────────────────────────────────────────

  Rule: copy things that change RARELY before things that change OFTEN.
""")


# ============================================================
# 4. BASE IMAGE CHOICES
# ============================================================

section("4. BASE IMAGE CHOICES — Size vs Compatibility")

print("""
  Not all Python base images are equal. Size matters for:
    - Pull speed (CI/CD pipelines downloading images)
    - Storage costs (ECR, Docker Hub storage)
    - Attack surface (more packages = more vulnerabilities)

  ┌────────────────────────────┬────────┬─────────────────────────────────┐
  │ Image                      │  Size  │ Notes                           │
  ├────────────────────────────┼────────┼─────────────────────────────────┤
  │ python:3.11                │ ~900MB │ Everything: build tools, dev    │
  │                            │        │ headers, full Debian. Use for   │
  │                            │        │ dev if you need compiling.      │
  ├────────────────────────────┼────────┼─────────────────────────────────┤
  │ python:3.11-slim           │ ~130MB │ Debian without build tools.     │
  │                            │        │ Most pure-Python packages work. │
  │  ← RECOMMENDED FOR DATA    │        │ Some C-ext packages need extra  │
  │    PIPELINES               │        │ apt packages (e.g. libpq-dev).  │
  ├────────────────────────────┼────────┼─────────────────────────────────┤
  │ python:3.11-alpine         │  ~50MB │ Minimal Alpine Linux.           │
  │                            │        │ GOTCHA: uses musl libc not glibc│
  │                            │        │ pandas, numpy, psycopg2 need    │
  │                            │        │ compilation → huge build times, │
  │                            │        │ or install pre-built wheels.    │
  │                            │        │ Avoid for data pipelines.       │
  ├────────────────────────────┼────────┼─────────────────────────────────┤
  │ python:3.11-bookworm       │ ~780MB │ Alias for python:3.11 (full     │
  │                            │        │ Debian Bookworm). Same as base. │
  ├────────────────────────────┼────────┼─────────────────────────────────┤
  │ python:3.11-slim-bookworm  │ ~130MB │ Explicit slim on Bookworm.      │
  │                            │        │ Same as python:3.11-slim.       │
  └────────────────────────────┴────────┴─────────────────────────────────┘

  RECOMMENDATION for data pipelines:
    Use python:3.11-slim (or python:3.11.9-slim for exact pinning).
    It handles pandas, numpy, sqlalchemy, psycopg2-binary without issues.

    If you need psycopg2 (not the binary), add:
      RUN apt-get update && apt-get install -y libpq-dev && rm -rf /var/lib/apt/lists/*

  PIN YOUR VERSIONS:
    python:3.11        → changes when 3.11.x patches release (unpredictable)
    python:3.11.9-slim → always exactly this version (reproducible builds)
    Use pinned versions in production Dockerfiles.
""")


# ============================================================
# 5. .DOCKERIGNORE
# ============================================================

section("5. .dockerignore — Exclude Files from the Build Context")

print("""
  When you run 'docker build .', Docker sends your entire directory
  (the "build context") to the Docker daemon before building.

  If your directory contains large data files, your .git history,
  or .venv, Docker sends all of that before even starting to build.
  This wastes time and inflates image size.

  .dockerignore works exactly like .gitignore — list patterns to exclude.
""")

DOCKERIGNORE = """
# Data files — large, don't belong in the image
data/
*.csv
*.parquet
*.xlsx
*.json.gz

# Git history — not needed in the image
.git/
.gitignore

# Virtual environment — will be reinstalled by pip
.venv/
venv/
env/

# Python cache — generated, not source
__pycache__/
*.pyc
*.pyo
*.pyd
.Python

# Jupyter notebooks — usually not needed in production
.ipynb_checkpoints/
*.ipynb

# SECRETS — never copy these into your image!
.env
.env.*
secrets/
*.pem
*.key

# Tests — don't include in production image
tests/
test_*
*_test.py

# IDE and OS
.idea/
.vscode/
.DS_Store
Thumbs.db

# dbt — build artifacts regenerated anyway
target/
dbt_packages/
logs/
"""

show_file(".dockerignore", DOCKERIGNORE)

print("""
  WHY .env must be in .dockerignore:
    If .env slips into your COPY . . instruction, your DB passwords
    and API keys are baked into the image layer permanently.
    Even if you delete them in a later RUN command, they're still
    visible in 'docker image history' and the image layer.

    The fix: .dockerignore prevents .env from ever entering the image.
    Use --env-file .env at runtime instead.
""")


# ============================================================
# 6. MULTI-STAGE BUILDS
# ============================================================

section("6. MULTI-STAGE BUILDS — Tiny Production Images")

print("""
  Problem: to build some Python packages, you need compilers and
  header files (gcc, libpq-dev, python3-dev, etc.).
  But you DON'T need those compilers at runtime — just the compiled files.

  Multi-stage builds let you:
    Stage 1 (builder): Install build tools, compile packages.
    Stage 2 (runtime): Start fresh, copy ONLY the compiled output.

  Result: production image has no build tools, no source code for deps,
  just your app and its installed packages.
""")

MULTISTAGE_DOCKERFILE = """
# ─────────── Stage 1: Builder ───────────
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies (only needed to compile packages)
RUN apt-get update && apt-get install -y \\
    gcc \\
    libpq-dev \\
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# ─────────── Stage 2: Runtime ───────────
FROM python:3.11-slim AS runtime

WORKDIR /app

# Install ONLY runtime system dependencies (not build tools)
RUN apt-get update && apt-get install -y \\
    libpq5 \\
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder stage
COPY --from=builder /root/.local /root/.local

# Copy application code
COPY . .

ENV PYTHONUNBUFFERED=1
ENV PATH=/root/.local/bin:$PATH

CMD ["python", "pipeline.py"]
"""

show_file("Dockerfile (multi-stage)", MULTISTAGE_DOCKERFILE)

print("""
  Size comparison:
    Single-stage with gcc + build tools: ~700MB
    Multi-stage (runtime only):          ~200MB

  The builder stage is used during build only — it doesn't end up
  in the final image. Docker discards it after copying what you need.

  Note: For most data pipelines using binary wheels (psycopg2-binary,
  pandas, numpy), multi-stage builds aren't necessary because binary
  wheels don't need compilation. Use multi-stage when:
    - Compiling custom C extensions
    - Building from source
    - Need to reduce image size significantly
""")


# ============================================================
# 7. SECURITY BEST PRACTICES
# ============================================================

section("7. SECURITY BEST PRACTICES")

print("""
  1. RUN AS NON-ROOT USER
  ────────────────────────
  By default, processes inside containers run as root.
  This is a security risk: if someone exploits your app,
  they get root access to the container (and potentially the host).

  Fix: create a non-root user and switch to it.
""")

NONROOT_SNIPPET = """
FROM python:3.11-slim

WORKDIR /app

# Create a non-root user
RUN useradd --create-home --shell /bin/bash appuser

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Switch to non-root user before CMD
USER appuser

ENV PYTHONUNBUFFERED=1
CMD ["python", "pipeline.py"]
"""

show_file("Dockerfile (non-root user)", NONROOT_SNIPPET)

print("""
  2. NEVER STORE SECRETS IN ENV IN DOCKERFILE
  ─────────────────────────────────────────────
  This is WRONG:

    ENV DB_PASSWORD=secret123   ← baked into the image permanently

  Anyone who pulls your image can run:
    docker image history my_pipeline:latest
  and see the password in the layer command.

  Also wrong:
    RUN export DB_PASSWORD=secret123 && python setup.py
  The password is visible in docker history even if you unset it.

  RIGHT: pass secrets at RUNTIME, not at build time:
    docker run -e DB_PASSWORD=$DB_PASSWORD my_pipeline:latest
    docker run --env-file .env my_pipeline:latest


  3. PIN EXACT VERSIONS FOR REPRODUCIBILITY
  ──────────────────────────────────────────
    FROM python:3.11          ← "latest 3.11.x" — changes over time
    FROM python:3.11.9-slim   ← exact version, always the same

  Pin base images in production. Use the full version tag.
  Check Docker Hub for available tags: hub.docker.com/_/python


  4. CLEAN UP APT CACHE IN THE SAME RUN LAYER
  ─────────────────────────────────────────────
  WRONG (cache takes up space in a layer):
    RUN apt-get update && apt-get install -y libpq-dev
    RUN rm -rf /var/lib/apt/lists/*   ← separate layer, doesn't help

  RIGHT (clean in the SAME RUN instruction):
    RUN apt-get update && apt-get install -y libpq-dev \\
        && rm -rf /var/lib/apt/lists/*
""")

demo(
    "docker image history my_pipeline:latest",
    note="See all layer commands — this is how secrets get exposed",
    explanation="""
  Output shows each layer's command:
    0B    CMD ["python" "pipeline.py"]
    1MB   COPY . .
    95MB  RUN pip install --no-cache-dir -r requirements.txt
    0B    ENV DB_PASSWORD=oops_my_secret     ← visible to anyone!
    2MB   COPY requirements.txt .
    ...
  If you accidentally baked a secret in, the only fix is a new image build.
    """
)


# ============================================================
# 8. COMPLETE PRODUCTION-QUALITY DOCKERFILE
# ============================================================

section("8. Complete Production-Quality Dockerfile for an ETL Pipeline")

PRODUCTION_DOCKERFILE = """
# ── Pin exact Python version for reproducibility ──
FROM python:3.11.9-slim

# ── Metadata (optional but good practice) ──
LABEL maintainer="data-team@company.com"
LABEL description="ETL pipeline: extracts from Postgres, loads to S3"

# ── Install OS dependencies (libpq for psycopg2, ca-certificates for SSL) ──
RUN apt-get update && apt-get install -y \\
    libpq5 \\
    ca-certificates \\
    && rm -rf /var/lib/apt/lists/*

# ── Set working directory ──
WORKDIR /app

# ── Create non-root user ──
RUN useradd --create-home --shell /bin/bash --uid 1001 appuser

# ── Copy and install dependencies FIRST (layer cache optimization) ──
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Copy application code AFTER dependencies ──
COPY . .

# ── Ensure non-root user owns the app directory ──
RUN chown -R appuser:appuser /app

# ── Runtime environment (NOT secrets!) ──
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# ── Switch to non-root user ──
USER appuser

# ── Default command ──
CMD ["python", "pipeline.py"]
"""

show_file("Dockerfile (production quality)", PRODUCTION_DOCKERFILE)

print("""
  Build it:
    docker build -t etl_pipeline:1.0.0 .

  Run it:
    docker run --rm --env-file .env etl_pipeline:1.0.0

  What makes this production-ready:
    - Pinned Python version (3.11.9-slim, not just 3.11)
    - apt cache cleaned in same RUN layer
    - requirements.txt copied before source code (layer cache)
    - Non-root user (security)
    - PYTHONUNBUFFERED=1 (logs appear immediately)
    - PYTHONDONTWRITEBYTECODE=1 (no .pyc files in container)
    - No secrets in Dockerfile (pass via --env-file at runtime)
    - Metadata labels for team documentation
""")

demo(
    "docker build -t etl_pipeline:1.0.0 .",
    note="Build the image from Dockerfile in current directory",
    explanation="""
  -t etl_pipeline:1.0.0    tag the image with name:version
  .                        build context: current directory

  Watch for cache hits in output:
    [1/7] FROM python:3.11.9-slim              CACHED
    [2/7] RUN apt-get install ...              CACHED
    [3/7] COPY requirements.txt .             CACHED
    [4/7] RUN pip install ...                  CACHED
    [5/7] COPY . .                             CACHE MISS  ← code changed
    ...
    """
)

demo(
    "docker build --no-cache -t etl_pipeline:1.0.0 .",
    note="Force full rebuild, ignoring all cached layers",
    explanation="""
  Use when:
    - Debugging a mysterious build issue
    - Base image has a security patch (want the latest)
    - Layer cache somehow got corrupted
  Avoid in normal development — slow.
    """
)


# ============================================================
# QUICK REFERENCE
# ============================================================

print()
print("=" * 70)
print("  QUICK REFERENCE — Dockerfile Instructions and Build Commands")
print("=" * 70)
print("""
  DOCKERFILE INSTRUCTIONS:
    FROM image:tag                base image (first instruction)
    WORKDIR /path                 set working directory
    COPY src dest                 copy files from machine to image
    RUN command                   execute command during build
    ENV KEY=VALUE                 set environment variable in image
    CMD ["cmd", "arg"]            default command (overridable)
    ENTRYPOINT ["cmd"]            fixed command (not overridable)
    USER username                 switch to non-root user
    LABEL key=value               metadata about the image
    ARG NAME=default              build-time variable (not runtime)
    EXPOSE port                   document which port app uses

  BUILD COMMANDS:
    docker build -t name:tag .    build image from Dockerfile
    docker build --no-cache .     rebuild without cache
    docker build -f other/Dockerfile .  use a different Dockerfile

  LAYER CACHE RULE:
    Copy files that change rarely BEFORE files that change often.
    requirements.txt → pip install → COPY code (not the other way around!)

  BASE IMAGE RECOMMENDATION:
    python:3.11-slim     best for most data pipelines
    python:3.11-alpine   avoid (pandas/numpy compilation issues)
    python:3.11          use in dev if you need build tools

  SECURITY CHECKLIST:
    [ ] .dockerignore includes .env, data/, .git/, .venv/
    [ ] No ENV DB_PASSWORD=... in Dockerfile
    [ ] Non-root USER before CMD
    [ ] Pinned image tag (3.11.9-slim not just 3.11)
    [ ] apt cache cleaned: && rm -rf /var/lib/apt/lists/*
    [ ] pip --no-cache-dir to avoid inflating image
""")
