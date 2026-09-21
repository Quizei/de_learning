"""
Docker for Data Engineers — Volumes, Networks, and Secrets
==========================================================
Three topics that seem boring until they bite you:

VOLUMES: Your pipeline writes results to /app/output/.
         You stop the container. The results are gone.
         Volumes fix this.

NETWORKS: Two containers can't talk to each other.
          Or they can, but to the wrong service.
          Networks and DNS fix this.

SECRETS: Your Postgres password is in the Docker image.
         It's in your git history. It's on Docker Hub.
         The right secrets pattern fixes this.

This file covers:
- Volume types: named volumes, bind mounts, tmpfs
- Volume lifecycle commands
- Network types: bridge, custom, host
- How Docker's internal DNS works
- The right and wrong ways to handle secrets
- Resource limits: memory and CPU for data pipelines
- Container inspection commands

Run this file: python3 04_volumes_networks_and_secrets.py
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
# 1. THE DATA LOSS PROBLEM
# ============================================================

section("1. THE DATA LOSS PROBLEM — Why Volumes Exist")

print("""
  Containers have EPHEMERAL (temporary) filesystems.
  Everything inside a container's filesystem exists only while
  the container exists. Remove the container, the data is gone.

  Conceptual demo of the problem:

    # Start a Postgres container, insert some data
    docker run -d --name mydb -e POSTGRES_PASSWORD=test postgres:15
    docker exec -it mydb psql -U postgres -c "CREATE TABLE users (id int);"
    docker exec -it mydb psql -U postgres -c "INSERT INTO users VALUES (1), (2), (3);"

    # Stop and remove the container
    docker stop mydb
    docker rm mydb

    # Start a NEW container from the same image
    docker run -d --name mydb -e POSTGRES_PASSWORD=test postgres:15
    docker exec -it mydb psql -U postgres -c "SELECT * FROM users;"
    # ERROR: relation "users" does not exist

    # The table — and all 3 rows — are GONE.
    # The image doesn't store runtime data, only the initial template.

  This is intentional: containers are supposed to be stateless and disposable.
  But your DATABASES need persistence.

  Volumes decouple the data from the container lifecycle.
  The container can be removed and recreated freely.
  The data persists in the volume.
""")


# ============================================================
# 2. VOLUME TYPES
# ============================================================

section("2. VOLUME TYPES — Named Volumes, Bind Mounts, tmpfs")

print("""
  Docker has three types of storage:

  ┌──────────────────┬───────────────┬─────────────────────────────────┐
  │ Type             │ Where stored  │ Best for                        │
  ├──────────────────┼───────────────┼─────────────────────────────────┤
  │ Named volume     │ Docker-managed│ Database data, persistent state  │
  │  -v pgdata:/data │ area on host  │ Data that must survive reboots  │
  ├──────────────────┼───────────────┼─────────────────────────────────┤
  │ Bind mount       │ Your chosen   │ Dev: live code, config files     │
  │  -v ./src:/app   │ host path     │ Dev only — not for prod          │
  ├──────────────────┼───────────────┼─────────────────────────────────┤
  │ tmpfs            │ Host RAM only │ Sensitive temp data, fast I/O    │
  │  --tmpfs /tmp    │ (in-memory)   │ Data that MUST NOT touch disk    │
  └──────────────────┴───────────────┴─────────────────────────────────┘
""")

print("""
  NAMED VOLUMES
  ─────────────
  Docker manages the storage location (usually /var/lib/docker/volumes/).
  You refer to it by name, not by path.
  Persists through 'docker stop', 'docker rm', even system restarts.
  Only destroyed when you explicitly remove it.
""")

demo(
    "docker volume create pgdata",
    note="Create a named volume (usually done automatically by docker run or compose)",
    explanation="""
  Creates a named volume 'pgdata'.
  In practice, docker run and docker-compose create volumes automatically.
  You rarely need to create them manually.
    """
)

demo(
    "docker run -d -e POSTGRES_PASSWORD=test -v pgdata:/var/lib/postgresql/data postgres:15",
    note="Use named volume: 'pgdata' is the volume, '/var/lib/postgresql/data' is where postgres stores files",
    explanation="""
  pgdata              — the named volume (Docker manages where it lives)
  /var/lib/postgresql/data  — path inside the container to mount it at

  If 'pgdata' doesn't exist, Docker creates it automatically.
  Postgres writes to /var/lib/postgresql/data inside container.
  That maps to the 'pgdata' volume on the host.
  Container removed → pgdata volume still exists → data safe.
    """
)

demo(
    "docker volume ls",
    note="List all named volumes",
    explanation="""
  Shows: DRIVER, VOLUME NAME
  Example:
    local   pgdata
    local   redis_data
    local   pipeline_pipeline_postgres_data   (compose project prefix)
    """
)

demo(
    "docker volume inspect pgdata",
    note="See where Docker is storing the volume data",
    explanation="""
  Shows the volume's metadata including Mountpoint:
    "Mountpoint": "/var/lib/docker/volumes/pgdata/_data"
  This is where the actual Postgres data files live on your host machine.
  On macOS with Docker Desktop, this path is inside a Linux VM.
    """
)

demo(
    "docker volume rm pgdata",
    note="Delete a named volume (and all its data)",
    explanation="""
  PERMANENT. All data in the volume is deleted.
  Can't delete if a container is using the volume.
  Stop and remove the container first.
  docker volume prune  — remove all unused (not attached to any container)
    """
)

print("""
  BIND MOUNTS
  ───────────
  Mount a specific directory from your machine into the container.
  Changes on your machine are immediately visible in the container.
  Changes in the container are immediately visible on your machine.
  The path must exist on your machine.
""")

demo(
    "docker run -v ./src:/app/src my_pipeline",
    note="Mount local ./src directory into the container at /app/src",
    explanation="""
  ./src  — path on YOUR machine (relative to current directory)
  /app/src — path INSIDE the container

  Use case: live code editing during development.
  Edit pipeline.py in your editor → container sees changes immediately.
  No rebuild needed. Massive dev speed boost.

  WARNING: Don't use bind mounts for production containers.
  Production should use the code baked into the image.
  Bind mounts for dev only.
    """
)

print("""
  TMPFS (IN-MEMORY)
  ─────────────────
  Stored entirely in RAM. Never written to disk.
  Destroyed when the container stops.
  Use for: temporary files with sensitive content, high-speed scratch space.
""")

demo(
    "docker run --tmpfs /tmp my_pipeline",
    note="Mount /tmp as in-memory storage (never hits disk)",
    explanation="""
  Files written to /tmp inside the container live in RAM.
  Faster than disk I/O. Automatically cleaned up on container stop.

  Data engineering use case: decrypt an encrypted file to /tmp for processing,
  process it, results go to persistent volume. Decrypted copy never touches disk.
    """
)


# ============================================================
# 3. NETWORKS
# ============================================================

section("3. NETWORKS — How Containers Talk to Each Other")

print("""
  Every container has its own network namespace — an isolated network stack.
  Containers can't communicate unless you explicitly connect them to a network.

  Docker Network Types:
    bridge  — default type, isolated from host, containers communicate via names
    host    — container shares host's network stack (Linux only)
    none    — no network access at all

  ┌──────────────────────────────────────────────────────────────┐
  │  YOUR MACHINE (host)                                         │
  │  IP: 192.168.1.50                                            │
  │                                                              │
  │  ┌──────────────────────────────────────────────────────┐   │
  │  │  Docker bridge network: pipeline_net                  │   │
  │  │  subnet: 172.18.0.0/16                                │   │
  │  │                                                        │   │
  │  │  ┌──────────────┐      ┌──────────────────────────┐   │   │
  │  │  │  postgres    │      │  pipeline                │   │   │
  │  │  │  172.18.0.2  │  ←── │  172.18.0.3              │   │   │
  │  │  │              │      │  DB_HOST=postgres        │   │   │
  │  │  └──────────────┘      └──────────────────────────┘   │   │
  │  └──────────────────────────────────────────────────────┘   │
  │                                                              │
  │  Port forwarding: 5432 (host) → 5432 (postgres container)   │
  └──────────────────────────────────────────────────────────────┘

  Docker runs an internal DNS server.
  Service names (postgres, pipeline, redis) resolve to their container IPs.
  The pipeline container can connect to "postgres:5432" — Docker resolves
  "postgres" to 172.18.0.2 automatically.

  You can't use 172.18.0.2 directly (changes on rebuild).
  You can't use "localhost" from another container.
  Use the SERVICE NAME. Always.
""")

demo(
    "docker network create pipeline_net",
    note="Create a custom bridge network",
    explanation="""
  Creates a named network 'pipeline_net'.
  Containers attached to this network can communicate by service name.
  docker-compose creates this automatically — manual creation only needed
  when manually running containers that need to talk to each other.
    """
)

demo(
    "docker run -d --name db --network pipeline_net -e POSTGRES_PASSWORD=test postgres:15",
    note="Start postgres container attached to pipeline_net",
    explanation="""
  --network pipeline_net  — attaches to the custom network
  Now 'db' is the hostname for this container on pipeline_net.
    """
)

demo(
    "docker run --rm --network pipeline_net my_pipeline python -c \"import psycopg2; conn = psycopg2.connect(host='db', ...)\"",
    note="Pipeline connects to postgres by the name 'db' (not 'localhost')",
    explanation="""
  Both containers on 'pipeline_net' → they can resolve each other's names.
  host='db' resolves to the postgres container's IP.
    """
)

demo(
    "docker network ls",
    note="List all networks",
    explanation="""
  Shows Docker's built-in networks + your custom ones:
    NETWORK ID    NAME             DRIVER    SCOPE
    a1b2c3d4e5f6  bridge           bridge    local   ← default
    g7h8i9j0k1l2  host             host      local   ← shares host network
    m3n4o5p6q7r8  none             null      local   ← no network
    s9t0u1v2w3x4  pipeline_net     bridge    local   ← your custom one
    """
)

demo(
    "docker network inspect pipeline_net",
    note="See all containers on this network and their IPs",
    explanation="""
  Shows every container attached to the network with its:
    - Container name
    - IP address within the network
    - Aliases (other names it responds to)
  Useful for debugging "why can't A talk to B?"
    """
)

print("""
  HOST NETWORK (Linux only):
    docker run --network host my_app

  Container uses the host's network stack directly.
  No port mapping needed: container's port 5432 IS host's port 5432.
  Highest network performance (no NAT overhead).

  Gotcha: doesn't work on macOS or Windows with Docker Desktop.
  Docker Desktop runs a Linux VM — containers are on the VM's network,
  not your macOS host. For macOS, stick with bridge networks.

  Data engineering use case: high-throughput data ingestion where
  NAT overhead matters. Only relevant on Linux servers.
""")


# ============================================================
# 4. SECRETS MANAGEMENT
# ============================================================

section("4. SECRETS MANAGEMENT — The Right and Wrong Ways")

print("""
  Secrets = DB passwords, API keys, tokens, encryption keys.
  Data pipelines connect to sensitive systems. Getting this wrong
  means credentials end up in git history or Docker Hub.

  The spectrum from worst to best:
""")

print("""
  ✗ WORST: Hardcoded in Dockerfile ENV instruction
  ─────────────────────────────────────────────────

  FROM python:3.11-slim
  ENV DB_PASSWORD=supersecret123    ← NEVER DO THIS
  CMD ["python", "pipeline.py"]

  Problems:
    1. The password is baked into the IMAGE LAYER permanently.
    2. Anyone who pulls the image can run 'docker history image:tag'
       and see the password in plaintext.
    3. If you push to Docker Hub, it's public.
    4. Even if you delete the ENV in a later instruction, the layer
       still exists in the image history.
    5. If the image is in git (unlikely but possible), it's in git history.

  There is no fix other than building a completely new image.
""")

demo(
    "docker image history etl_pipeline:latest",
    note="This is how leaked secrets are discovered (or exploited)",
    explanation="""
  Output might show:
    SIZE     CREATED BY
    0B       CMD ["python" "pipeline.py"]
    1.2MB    COPY . .
    87MB     pip install -r requirements.txt
    0B       ENV DB_PASSWORD=supersecret123    ← visible to anyone
    0B       WORKDIR /app
    130MB    python:3.11-slim

  This command is in Docker's public documentation.
  Attackers run it on any image they suspect has secrets.
    """
)

print("""
  ✗ WRONG: Hardcoded in docker-compose.yml (ends up in git)
  ──────────────────────────────────────────────────────────

  services:
    pipeline:
      environment:
        DB_PASSWORD: supersecret123    ← if docker-compose.yml is in git...

  docker-compose.yml gets committed to git.
  Now it's in git history forever, even if you remove it in a later commit.

  ✓ CORRECT: Pass from host environment
  ──────────────────────────────────────
  Set the variable in your shell, reference it in docker-compose.yml:

    # In your shell:
    export DB_PASSWORD=supersecret123

    # In docker-compose.yml:
    environment:
      DB_PASSWORD: ${DB_PASSWORD}    ← reads from host environment

    # Or on command line:
    docker run -e DB_PASSWORD=$DB_PASSWORD my_pipeline

  The value lives only in your shell environment, not in any file.
""")

print("""
  ✓ CORRECT: .env file with docker-compose (never commit .env)
  ──────────────────────────────────────────────────────────────
  This is the most common pattern for local development.

    # .env file (in .gitignore — NEVER commit)
    DB_PASSWORD=supersecret123
    API_KEY=abc123xyz

    # docker-compose.yml
    services:
      pipeline:
        env_file:
          - .env      ← loads all variables from .env

    # .gitignore
    .env
    .env.local
    .env.*.local

  Workflow:
    1. Create .env.example with placeholder values (commit this to git)
    2. Each developer copies: cp .env.example .env
    3. Each developer fills in real values in their local .env
    4. .env is gitignored — never leaves the machine

  ✓ CORRECT: Fetch secrets from a secrets manager at startup
  ──────────────────────────────────────────────────────────

  Best practice for production. In your pipeline.py:

    import boto3  # AWS SDK
    import json

    def get_secret(secret_name):
        client = boto3.client('secretsmanager', region_name='us-east-1')
        response = client.get_secret_value(SecretId=secret_name)
        return json.loads(response['SecretString'])

    # At pipeline startup:
    secrets = get_secret('prod/pipeline/db-credentials')
    db_password = secrets['password']

  The container only needs IAM permissions (via an instance profile or
  ECS task role) — no passwords in .env, no passwords in env vars.
  Secrets are fetched fresh each run. Rotate without redeploying.

  ✓ CORRECT: Docker Secrets (Swarm) or Kubernetes Secrets
  ─────────────────────────────────────────────────────────
  Docker Secrets (for Docker Swarm mode):
    docker secret create db_password - <<< "supersecret123"
    Mounted as a file inside the container: /run/secrets/db_password
    Your code reads the file — the secret never appears in env vars.

  Kubernetes Secrets:
    kubectl create secret generic db-creds --from-literal=password=supersecret
    Mounted as env var or file in the pod.

  Overkill for local development, but required for production orchestration.
""")

print("""
  SECRETS CHECKLIST FOR DATA PIPELINES:
  ──────────────────────────────────────
    [ ] No secrets in Dockerfile (no ENV with passwords/keys)
    [ ] No secrets hardcoded in docker-compose.yml
    [ ] .env in .gitignore (check: git status should never show .env)
    [ ] .env.example committed with placeholder values
    [ ] Production uses secrets manager (AWS Secrets Manager, Vault, etc.)
    [ ] After any accidental commit of secrets: rotate immediately
        (Removing from git history is hard — just rotate the credential)
""")


# ============================================================
# 5. RESOURCE LIMITS
# ============================================================

section("5. RESOURCE LIMITS — Protecting Your Machine from Your Pipeline")

print("""
  Data pipelines can consume unlimited resources by default.
  A pandas operation on a 10GB CSV will try to allocate 10GB+ of RAM.
  Without limits, it kills your machine or starves other containers.

  Set limits to:
    - Prevent one pipeline from killing your whole stack
    - Simulate production constraints during testing
    - Ensure predictable behavior across environments
""")

demo(
    "docker run --memory 2g --cpus 1.5 my_pipeline",
    note="Limit to 2GB RAM and 1.5 CPU cores",
    explanation="""
  --memory 2g      — container can use at most 2GB RAM
                     If it tries to use more: OOM kill (process killed)
  --cpus 1.5       — container can use at most 1.5 CPU cores
                     On a 4-core machine, this leaves 2.5 cores for other things
  --memory-swap 2g — set same as --memory to disable swap (recommended)
    """
)

demo(
    "docker run --memory 512m --memory-swap 512m my_pipeline",
    note="512MB RAM, no swap (hard limit — fails fast if exceeded)",
    explanation="""
  Setting --memory-swap equal to --memory disables swap.
  Container hits the 512MB limit → immediate OOM kill, no slow swapping.
  Useful for testing: "does my pipeline actually fit in 512MB?"
    """
)

print("""
  In docker-compose.yml (Compose v2 syntax):

  services:
    pipeline:
      build: .
      deploy:
        resources:
          limits:
            memory: 2G
            cpus: "1.5"
          reservations:
            memory: 512M
            cpus: "0.5"

  limits:       — hard ceiling (container killed if exceeded)
  reservations: — guaranteed minimum (Docker won't start if unavailable)

  Data engineering scenarios:
    - pandas on 1GB CSV: needs ~3-5GB RAM → set limit to 6G + alert if near limit
    - nightly batch job: limit to 4G so it doesn't block daytime work
    - test containers: limit to 512M to catch memory leaks early
""")

demo(
    "docker stats",
    note="Live resource usage for all running containers",
    explanation="""
  Shows continuously updating table:
    CONTAINER       CPU%    MEM USAGE / LIMIT    MEM%    NET I/O    BLOCK I/O
    pipeline_app    12.5%   1.2GB / 4GB          30%     ...

  Ctrl+C to exit.
  docker stats container_name  — just one container
  docker stats --no-stream     — one snapshot (no live updates, scriptable)
    """
)


# ============================================================
# 6. CONTAINER INSPECTION COMMANDS
# ============================================================

section("6. INSPECTING CONTAINERS — Debug and Understand State")

demo(
    "docker inspect my_pipeline",
    note="Full JSON dump of everything about the container",
    explanation="""
  Enormous output. Contains:
    - Network settings (IP, ports, networks)
    - Mounts (volumes attached)
    - Environment variables
    - Config (CMD, ENTRYPOINT, labels)
    - State (running, exit code, etc.)
    - Resource limits

  Filter with --format:
    docker inspect --format='{{.State.Status}}' my_pipeline
    docker inspect --format='{{.NetworkSettings.IPAddress}}' my_pipeline
    """
)

demo(
    "docker exec my_pipeline env",
    note="List ALL environment variables inside a running container",
    explanation="""
  Shows every env var the container has, including:
    - Variables set in Dockerfile (ENV instructions)
    - Variables passed via -e or --env-file
    - System variables (PATH, HOME, etc.)

  Useful for: "is my .env loading correctly?" or "what PATH does the container see?"
  Security note: if someone can run 'docker exec', they can see all your env vars.
  This is why secrets in env vars are still a risk — anyone with Docker access can read them.
    """
)

demo(
    "docker exec my_pipeline df -h",
    note="Check disk space inside the container's filesystem",
    explanation="""
  Check if the container is running out of disk space.
  Each container has an overlay filesystem — limited by the Docker storage driver.
  Default limit is usually generous (100GB+), but worth checking for long-running containers.
    """
)

demo(
    "docker exec my_pipeline cat /proc/meminfo",
    note="Check memory info from inside the container",
    explanation="""
  On Linux, /proc/meminfo shows memory stats.
  Note: inside the container, it shows host memory by default.
  For container-scoped memory limits, use 'docker stats' instead.
    """
)


# ============================================================
# QUICK REFERENCE
# ============================================================

print()
print("=" * 70)
print("  QUICK REFERENCE — Volumes, Networks, Secrets, Resources")
print("=" * 70)
print("""
  VOLUMES:
    docker volume create NAME           create named volume
    docker volume ls                    list all volumes
    docker volume inspect NAME          see volume details + mountpoint
    docker volume rm NAME               delete volume (and its data)
    docker volume prune                 delete all unused volumes
    -v NAME:/container/path             named volume in docker run
    -v ./host/path:/container/path      bind mount (dev only)
    --tmpfs /container/path             in-memory (no disk persistence)

  NETWORKS:
    docker network create NAME          create custom bridge network
    docker network ls                   list networks
    docker network inspect NAME         see containers on network
    docker network rm NAME              delete network
    --network NAME                      attach container to network

  SERVICE NAMING RULE:
    Inside Docker networks, use SERVICE NAMES as hostnames.
    "postgres" not "localhost", "redis" not "127.0.0.1"

  SECRETS — RANKED FROM WORST TO BEST:
    ✗ ENV DB_PASS=secret in Dockerfile    (baked in image, visible in history)
    ✗ hardcoded in docker-compose.yml    (ends up in git)
    ✓ -e DB_PASS=$DB_PASS                (from shell environment)
    ✓ env_file: .env  (+.gitignore .env) (local dev standard)
    ✓ AWS Secrets Manager / Vault        (production standard)
    ✓ Docker Secrets / K8s Secrets       (orchestration standard)

  RESOURCE LIMITS:
    --memory 2g                          max 2GB RAM
    --cpus 1.5                           max 1.5 CPU cores
    docker stats                         live resource usage

  INSPECT:
    docker inspect container             full JSON info
    docker exec container env            see environment variables
    docker stats                         live CPU + memory usage
""")
