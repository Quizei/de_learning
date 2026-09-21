# Week 3: Docker for Data Pipelines

## What This Week Covers

"Works on my machine" is the most expensive phrase in data engineering.
Docker packages your pipeline code, Python version, and all dependencies
into a single portable container that runs identically everywhere.

This week takes you from zero Docker knowledge to running a complete
containerized local data stack — Postgres + your pipeline — with one command.

## Topics

### Concept 1 — Docker Concepts: Images and Containers
- The problem Docker solves: "works on my machine" across Python versions, OS, packages
- Core concepts: Image (blueprint) vs Container (running instance) vs Registry (image store)
- Layers: how Docker caches builds for fast rebuilds
- Docker architecture: CLI → daemon → registry
- Essential commands: `docker pull`, `docker run`, `docker ps`, `docker logs`, `docker exec`
- Port mapping (`-p 5432:5432`), volume mounting (`-v`), environment variables (`--env-file`)
- Container lifecycle: pull → run → stop → rm
- Data engineer pattern: throwaway Postgres in one command — zero installation

### Concept 2 — Writing Dockerfiles for Python Data Apps
- Dockerfile anatomy: `FROM`, `WORKDIR`, `COPY`, `RUN`, `ENV`, `CMD` — every instruction explained
- Layer caching: the single biggest optimization — copy `requirements.txt` before source code
- Base image comparison: `python:3.11` (900MB) vs `python:3.11-slim` (130MB) vs `python:3.11-alpine` (50MB, avoid)
- `.dockerignore`: exclude data files, `.git`, `.venv`, `.env`, `__pycache__`
- Multi-stage builds: build stage with compilers, runtime stage without them
- Security best practices: non-root user, no secrets in `ENV`, pin versions, clean apt cache

### Concept 3 — Docker Compose for Data Stacks
- Why docker-compose: coordinate multiple containers with one file and one command
- `docker-compose.yml` structure: services, volumes, networks — all fields explained
- Service networking: why `DB_HOST=postgres` not `DB_HOST=localhost`
- `depends_on` with `condition: service_healthy` — proper startup ordering
- Health checks: `pg_isready` for Postgres, `redis-cli ping` for Redis
- Essential commands: `up -d`, `logs -f`, `exec`, `ps`, `down`, `down -v`
- Environment files: `env_file:`, variable substitution `${VAR}`, per-service config
- Override files: `docker-compose.override.yml` for dev vs prod differences

### Concept 4 — Volumes, Networks, and Secrets
- Volume types: named volumes (persist data), bind mounts (dev live-reload), tmpfs (in-memory)
- Volume commands: `docker volume ls`, `docker volume inspect`, `docker volume rm`
- Networks: bridge (default), custom networks, host (Linux only)
- Docker DNS: service names resolve to container IPs — how `postgres` becomes an address
- Secrets — ranked worst to best: `ENV` in Dockerfile → hardcoded in compose → `.env` file → secrets manager
- `docker image history` — how leaked secrets are visible in layer history
- Resource limits: `--memory 2g`, `--cpus 1.5` — why data pipelines need them
- Container inspection: `docker inspect`, `docker exec container env`, `docker stats`

## Folder Structure

```
week_03_docker_for_data_pipelines/
  concepts/
    01_docker_concepts_images_containers.py   — run me: core Docker model + commands
    02_dockerfile_for_python_data_apps.py     — run me: Dockerfile anatomy + caching
    03_docker_compose_data_stacks.py          — run me: compose + networking
    04_volumes_networks_and_secrets.py        — run me: data persistence + security
  practice/
    exercises.py                              — 7 exercises with solutions
  projects/
    containerized_pipeline_stack/
      Dockerfile                              — production-quality Python image
      docker-compose.yml                      — postgres + pipeline stack
      pipeline.py                             — ETL app with retry logic
      requirements.txt                        — pinned dependencies
      Makefile                                — shortcut commands
      .env.example                            — config template (commit this)
      README.md                               — one-command setup guide
```

## How to Use This Week

### 1. Read the concept files

```bash
python3 concepts/01_docker_concepts_images_containers.py
python3 concepts/02_dockerfile_for_python_data_apps.py
python3 concepts/03_docker_compose_data_stacks.py
python3 concepts/04_volumes_networks_and_secrets.py
```

Each file prints commands and explanations. No Docker needed to read them.
The files are designed to be readable as educational material.

### 2. Work through the exercises

```bash
python3 practice/exercises.py setup    # print setup instructions
python3 practice/exercises.py          # print all exercises + solutions
```

Exercises 1-2 require Docker running. Exercises 3-7 are conceptual.
Try each one before reading the solution.

### 3. Run the project

```bash
cd projects/containerized_pipeline_stack

cp .env.example .env
# Edit .env: change DB_PASSWORD and POSTGRES_PASSWORD to any value

make up           # build + start postgres + pipeline
make logs         # watch output (Ctrl+C to stop)
make psql         # connect to DB and inspect pipeline_runs table
make run          # run the pipeline again
make down         # stop everything (data preserved)
make clean        # stop + delete all data (fresh start)
```

## Practice Goals

- [ ] Pull `python:3.11-slim` and `postgres:15`, compare sizes, explore what's inside with `docker run -it --rm`
- [ ] Write a Dockerfile for a pandas pipeline with correct layer order — verify code changes rebuild in seconds not minutes
- [ ] Write a `docker-compose.yml` with a Postgres service that has a healthcheck and `depends_on: condition: service_healthy`
- [ ] Debug a container that exits immediately: know the `docker-compose logs` → read traceback → fix cycle
- [ ] Explain the difference between `docker-compose down` and `docker-compose down -v`
- [ ] Run the containerized pipeline stack: `make up`, inspect `pipeline_runs` table with `make psql`, run pipeline multiple times

## Key Commands Cheat Sheet

```bash
# ── Images ──────────────────────────────────────────────────────
docker pull python:3.11-slim          # download image
docker images                         # list local images
docker rmi image:tag                  # remove image
docker image history image:tag        # see layers (and spot leaked secrets)
docker image prune                    # remove unused images

# ── Run containers ───────────────────────────────────────────────
docker run --rm image CMD             # run + auto-remove on exit
docker run -it --rm image bash        # interactive shell
docker run -d --name NAME image       # background with name
docker run -p 5432:5432 image         # map port (host:container)
docker run -v ./data:/app/data image  # mount local directory
docker run --env-file .env image      # load env vars from file
docker run --memory 2g --cpus 1.5 image  # resource limits

# ── Manage containers ────────────────────────────────────────────
docker ps                             # running containers
docker ps -a                          # all containers
docker logs -f container              # follow logs live
docker exec -it container bash        # shell into running container
docker stop container                 # graceful stop
docker rm -f container                # force stop + remove
docker stats                          # live resource usage

# ── Throwaway Postgres (data engineer staple) ────────────────────
docker run --rm -e POSTGRES_PASSWORD=test -p 5432:5432 postgres:15

# ── docker-compose ───────────────────────────────────────────────
docker-compose up -d                  # start all (detached)
docker-compose up --build             # rebuild images then start
docker-compose logs -f                # follow all logs
docker-compose logs -f service        # follow one service
docker-compose exec service CMD       # run in running container
docker-compose run --rm service CMD   # one-off container
docker-compose ps                     # service status
docker-compose down                   # stop + remove containers
docker-compose down -v                # also remove volumes

# ── Volumes ──────────────────────────────────────────────────────
docker volume ls                      # list volumes
docker volume inspect NAME            # see volume details
docker volume prune                   # remove unused volumes

# ── Networks ─────────────────────────────────────────────────────
docker network ls                     # list networks
docker network inspect NAME           # see containers on network

# ── Debug ────────────────────────────────────────────────────────
docker inspect container              # full container JSON
docker exec container env             # see all env vars
docker image history image:tag        # see image layers (security audit)
```
