"""
Week 5 Practice Exercises — AWS CLI, Environments, Makefiles, SSH
==================================================================
Seven practical exercises covering the tools from this week.
Work through each one. Answers are at the bottom of each exercise.

Topics covered:
  Exercise 1: AWS CLI S3 Operations
  Exercise 2: Secrets Manager vs .env
  Exercise 3: Full Environment Setup
  Exercise 4: Makefile for a dbt Project
  Exercise 5: SSH Config and Tunneling
  Exercise 6: Monitoring Scenario — High Memory
  Exercise 7: Project Audit — Security and Best Practices

Run this file: python3 practice/exercises.py
The file prints all exercises and sets up a mock project for exercise 3.
"""

import os
import subprocess
import tempfile
import shutil


# ============================================================
# HELPERS
# ============================================================

def section(title):
    print()
    print("=" * 70)
    print(f"  {title}")
    print("=" * 70)


def exercise(number, title):
    print()
    print("-" * 70)
    print(f"  EXERCISE {number}: {title}")
    print("-" * 70)


def answer_header():
    print()
    print("  ── ANSWER ───────────────────────────────────────────────────────────")


# ============================================================
# EXERCISE 1: AWS CLI S3
# ============================================================

exercise(1, "AWS CLI S3 Operations")

print("""
  You have an S3 bucket named 'acme-data-lake' with raw data landing in
  the prefix 'raw/'.  A processed output folder lives in 'processed/'.

  Write the AWS CLI commands for each task below.
  (You can assume your credentials are configured for a dev account.)

  TASKS:
  ─────────────────────────────────────────────────────────────────────
  a) List all objects in the 'raw/' prefix, recursively.

  b) Upload a single file 'orders_2024-01-15.csv' from your current
     directory to 'raw/orders/'.

  c) Sync your local './processed/' directory up to 'processed/',
     excluding any .tmp files and any files starting with '.'.

  d) Generate a presigned URL for 'processed/report_q4.pdf' that
     expires in 24 hours. (24 hours = 86400 seconds)

  e) Find all objects in the bucket larger than 1 GB.
     Hint: combine aws s3api list-objects with jq.

  f) List all .parquet files in the raw/ prefix only (not recursive)
     and count how many there are.

  Write your answers before reading the answer below.
""")

answer_header()
print("""
  a) List raw/ recursively:
     $ aws s3 ls s3://acme-data-lake/raw/ --recursive

  b) Upload single file:
     $ aws s3 cp orders_2024-01-15.csv s3://acme-data-lake/raw/orders/

  c) Sync with exclusions:
     $ aws s3 sync ./processed/ s3://acme-data-lake/processed/ \\
         --exclude "*.tmp" --exclude ".*"

  d) Presigned URL (24 hours):
     $ aws s3 presign s3://acme-data-lake/processed/report_q4.pdf \\
         --expires-in 86400

  e) Find files > 1 GB (1073741824 bytes):
     $ aws s3api list-objects --bucket acme-data-lake \\
         | jq '.Contents[] | select(.Size > 1073741824) | {Key, Size}'

     Or using --query (size comparison requires jq):
     $ aws s3api list-objects-v2 --bucket acme-data-lake \\
         | jq '[.Contents[] | select(.Size > 1073741824)] | sort_by(.Size) | reverse'

  f) Count .parquet files in raw/ (non-recursive):
     $ aws s3 ls s3://acme-data-lake/raw/ | grep '.parquet' | wc -l

     For truly reliable parquet counting (using api):
     $ aws s3api list-objects-v2 --bucket acme-data-lake --prefix 'raw/' --delimiter '/' \\
         --query 'Contents[?ends_with(Key, `.parquet`)].Key' --output text | wc -w
""")


# ============================================================
# EXERCISE 2: Secrets Manager vs .env
# ============================================================

exercise(2, "Secrets Manager vs .env — Rewrite a Pipeline")

print("""
  You inherited a pipeline.py that reads credentials from a .env file.
  The team is moving it to production on EC2.

  CURRENT CODE (pipeline.py — the bad version):
  ─────────────────────────────────────────────────────────────────────

    import os
    from dotenv import load_dotenv
    import sqlalchemy

    load_dotenv()  # reads .env file

    DB_HOST     = os.environ["DB_HOST"]
    DB_PORT     = os.environ["DB_PORT"]
    DB_NAME     = os.environ["DB_NAME"]
    DB_USER     = os.environ["DB_USER"]
    DB_PASSWORD = os.environ["DB_PASSWORD"]  # ← stored in .env file on server

    engine = sqlalchemy.create_engine(
        f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    )

  TASKS:
  ─────────────────────────────────────────────────────────────────────
  a) Rewrite get_db_engine() to fetch credentials from AWS Secrets
     Manager instead of a .env file. The secret name is 'prod/db/postgres'.
     The secret JSON has keys: host, port, dbname, username, password.

  b) Explain: when would you STILL use a .env file in this project?

  c) What IAM permission does the EC2 instance role need to fetch
     this specific secret?

  Write your answers before reading the answer below.
""")

answer_header()
print("""
  a) Rewritten pipeline.py using Secrets Manager:

    import boto3
    import json
    import sqlalchemy

    def get_db_credentials(secret_name: str, region: str = "us-east-1") -> dict:
        \"\"\"Fetch database credentials from AWS Secrets Manager.\"\"\"
        client = boto3.client("secretsmanager", region_name=region)
        response = client.get_secret_value(SecretId=secret_name)
        return json.loads(response["SecretString"])

    def get_db_engine() -> sqlalchemy.engine.Engine:
        creds = get_db_credentials("prod/db/postgres")
        url = (
            f"postgresql://{creds['username']}:{creds['password']}"
            f"@{creds['host']}:{creds['port']}/{creds['dbname']}"
        )
        return sqlalchemy.create_engine(url)

    # Usage:
    engine = get_db_engine()

    Key improvements:
      - No .env file on the server (nothing to accidentally cat/print)
      - EC2 instance uses its IAM role — no long-lived keys
      - Secrets Manager supports rotation (passwords change automatically)
      - Audit trail: every get_secret_value call is logged in CloudTrail

  b) When you'd STILL use .env in this project:
     - Local development on your laptop (for quick iteration)
     - .env holds non-sensitive config like feature flags, local DB URLs
     - The .env is in .gitignore and NEVER has production passwords
     - Running the pipeline locally doesn't need real prod credentials

     Rule: .env is fine for dev. Secrets Manager is required for prod.

  c) Required IAM permission on the EC2 instance role:
     {
       "Effect": "Allow",
       "Action": "secretsmanager:GetSecretValue",
       "Resource": "arn:aws:secretsmanager:us-east-1:123456789012:secret:prod/db/postgres-*"
     }

     Principle of least privilege:
       - Only GetSecretValue (not create, update, delete)
       - Only this specific secret's ARN (not *)
       - No access to staging or other prod secrets
""")


# ============================================================
# EXERCISE 3: Full Environment Setup
# ============================================================

exercise(3, "Full Environment Setup — Step by Step")

print("""
  Walk through setting up a new Python project from scratch with all
  best practices: pyenv version pinning, venv, requirements management,
  and a proper .gitignore.

  You're creating a project called 'customer_churn_pipeline'.

  TASKS:
  ─────────────────────────────────────────────────────────────────────
  Write the EXACT sequence of commands to:

  a) Create and enter the project directory.

  b) Pin Python 3.11.6 for this project using pyenv (creates .python-version).

  c) Create a virtual environment in .venv.

  d) Activate the venv.

  e) Create requirements.in with these direct dependencies:
       pandas, sqlalchemy, psycopg2-binary, boto3, click

  f) Install pip-tools and compile requirements.txt from requirements.in.

  g) Create a .gitignore that excludes the right things.

  h) Initialize git and make the first commit.

  i) What files should you commit? What should you NOT commit?

  Write your answers before reading the answer below.
""")

answer_header()
print("""
  a) Create project directory:
     $ mkdir customer_churn_pipeline && cd customer_churn_pipeline

  b) Pin Python version:
     $ pyenv local 3.11.6
     # Creates .python-version with content: "3.11.6"
     # Commit this file — teammates will use the same version

  c) Create venv (using the pyenv-pinned Python):
     $ python -m venv .venv

  d) Activate:
     $ source .venv/bin/activate
     # Prompt now shows: (.venv) user@machine customer_churn_pipeline $

  e) Create requirements.in:
     $ cat > requirements.in << 'EOF'
     pandas>=2.0
     sqlalchemy>=2.0
     psycopg2-binary
     boto3
     click>=8.0
     EOF

  f) Install pip-tools and compile:
     $ pip install pip-tools
     $ pip-compile requirements.in
     # Creates requirements.txt with ALL transitive deps pinned
     $ pip install -r requirements.txt

  g) Create .gitignore:
     $ cat > .gitignore << 'EOF'
     # Python
     .venv/
     __pycache__/
     *.pyc
     *.pyo
     .eggs/
     *.egg-info/
     dist/
     build/

     # Environment
     .env
     .env.*
     !.env.example

     # Tools
     .pytest_cache/
     .coverage
     htmlcov/
     .ruff_cache/
     .mypy_cache/

     # OS
     .DS_Store
     Thumbs.db

     # Data files (don't commit raw data)
     *.csv
     *.parquet
     *.json
     data/
     !data/.gitkeep
     EOF

  h) Initialize git and first commit:
     $ git init
     $ git add .python-version requirements.in requirements.txt .gitignore
     $ git commit -m "feat: initial project setup with pinned Python and deps"

  i) COMMIT: .python-version, requirements.in, requirements.txt, .gitignore,
             src/ code, tests/, Makefile, pyproject.toml, .env.example

     DO NOT COMMIT: .venv/, .env, *.csv, *.parquet, __pycache__/, *.pyc
""")

# Actually demonstrate creating a temp mock project structure
print("""
  ── LIVE DEMO: Creating mock project structure ───────────────────────
""")

tmpdir = tempfile.mkdtemp(prefix="ex3_demo_")
project_dir = os.path.join(tmpdir, "customer_churn_pipeline")
os.makedirs(os.path.join(project_dir, "src"))
os.makedirs(os.path.join(project_dir, "tests"))

# Create files
files_to_create = {
    ".python-version": "3.11.6\n",
    "requirements.in": "pandas>=2.0\nsqlalchemy>=2.0\npsycopg2-binary\nboto3\nclick>=8.0\n",
    ".gitignore": ".venv/\n__pycache__/\n*.pyc\n.env\n*.csv\ndata/\n",
    "src/__init__.py": "",
    "src/pipeline.py": "# customer churn pipeline\n",
    "tests/__init__.py": "",
    "tests/test_pipeline.py": "# tests\n",
    ".env.example": "DB_HOST=localhost\nDB_PORT=5432\nDB_NAME=churn\nDB_USER=\nDB_PASSWORD=\n",
}

for filepath, content in files_to_create.items():
    full_path = os.path.join(project_dir, filepath)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, "w") as f:
        f.write(content)

print(f"  Created mock project in: {project_dir}")
print()

result = subprocess.run(
    f"find {project_dir} -type f | sed 's|{project_dir}/||' | sort",
    shell=True, capture_output=True, text=True
)
print("  Project structure:")
for line in result.stdout.strip().splitlines():
    print(f"    {line}")

shutil.rmtree(tmpdir)
print(f"\n  (Cleaned up temp directory.)")


# ============================================================
# EXERCISE 4: Makefile for a dbt Project
# ============================================================

exercise(4, "Makefile Writing — dbt Project")

print("""
  Write a complete Makefile for a dbt project with the following structure:
    my_dbt_project/
    ├── Makefile        ← you write this
    ├── dbt/
    │   ├── dbt_project.yml
    │   └── models/
    ├── .venv/
    └── requirements-dev.txt

  The Makefile should have these targets:
    install      Create venv and install requirements-dev.txt
    dbt-run      Run all dbt models (cd dbt && dbt run)
    dbt-test     Run all dbt tests
    dbt-run-prod Run dbt with the prod profile (--target prod)
    lint         Run sqlfluff on the dbt models
    clean        Remove pycache and dbt artifacts
    help         Auto-generated from ## comments

  Requirements:
    - Use variables for PYTHON, VENV, DBT, SQLFLUFF
    - .DEFAULT_GOAL should be help
    - .PHONY for all targets
    - Each target should have a ## comment for the help system
    - The dbt commands should cd into the dbt/ directory

  Write your answer before reading the answer below.
""")

answer_header()
print(r"""
  .PHONY: install dbt-run dbt-test dbt-run-prod lint clean help

  PYTHON    := python3
  VENV      := .venv
  PIP       := $(VENV)/bin/pip
  DBT       := $(VENV)/bin/dbt
  SQLFLUFF  := $(VENV)/bin/sqlfluff

  .DEFAULT_GOAL := help

  install: ## Create venv and install all dependencies
  	$(PYTHON) -m venv $(VENV)
  	$(PIP) install --upgrade pip
  	$(PIP) install -r requirements-dev.txt

  dbt-run: ## Run all dbt models against the default (dev) target
  	cd dbt && $(DBT) run

  dbt-test: ## Run all dbt data quality tests
  	cd dbt && $(DBT) test

  dbt-run-prod: ## Run all dbt models against the production target
  	cd dbt && $(DBT) run --target prod

  lint: ## Check SQL style with sqlfluff
  	$(SQLFLUFF) lint dbt/models/

  clean: ## Remove Python bytecode and dbt target artifacts
  	find . -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
  	find . -name '*.pyc' -delete 2>/dev/null || true
  	rm -rf dbt/target/ dbt/dbt_packages/

  help: ## Show available targets
  	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
  		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'
""")


# ============================================================
# EXERCISE 5: SSH Config and Tunneling
# ============================================================

exercise(5, "SSH Config and Tunneling")

print("""
  Your team has three EC2 servers:
    dev:     54.10.20.30   (Ubuntu, key: ~/.ssh/dev.pem)
    staging: 54.10.20.31   (Ubuntu, key: ~/.ssh/staging.pem)
    prod:    54.10.20.32   (Amazon Linux → ec2-user, key: ~/.ssh/prod.pem)

  Production has a Postgres RDS at:  prod-db.cluster.us-east-1.rds.amazonaws.com:5432
  (Not publicly accessible — only reachable from the prod EC2 server)

  The prod EC2 also runs an Airflow webserver on port 8080 (internal only).

  TASKS:
  ─────────────────────────────────────────────────────────────────────
  a) Write a ~/.ssh/config that defines aliases for all three servers.
     Add keepalive settings so long-running sessions don't timeout.

  b) Write the command to tunnel prod Postgres so you can connect
     from your local machine using: psql -h localhost -p 5432

  c) Write the command to tunnel the prod Airflow UI so you can
     open http://localhost:8080 in your browser.

  d) Write the command to copy a file 'fix.py' to the staging server's
     /app/src/ directory.

  e) Write the command to tail /var/log/etl.log on prod without
     starting an interactive shell.

  Write your answers before reading the answer below.
""")

answer_header()
print("""
  a) ~/.ssh/config:

     Host pipeline-dev
         HostName 54.10.20.30
         User ubuntu
         IdentityFile ~/.ssh/dev.pem
         ServerAliveInterval 60
         ServerAliveCountMax 3

     Host pipeline-staging
         HostName 54.10.20.31
         User ubuntu
         IdentityFile ~/.ssh/staging.pem
         ServerAliveInterval 60
         ServerAliveCountMax 3

     Host pipeline-prod
         HostName 54.10.20.32
         User ec2-user
         IdentityFile ~/.ssh/prod.pem
         ServerAliveInterval 60
         ServerAliveCountMax 3

  b) Tunnel prod Postgres:
     $ ssh -L 5432:prod-db.cluster.us-east-1.rds.amazonaws.com:5432 pipeline-prod
     # Keep this terminal open. In another terminal:
     $ psql -h localhost -p 5432 -U etl_user -d prod_db

     Background version (no shell, just the tunnel):
     $ ssh -N -f -L 5432:prod-db.cluster.us-east-1.rds.amazonaws.com:5432 pipeline-prod

  c) Tunnel Airflow UI:
     $ ssh -L 8080:localhost:8080 pipeline-prod
     # Then open http://localhost:8080 in your browser

     Background version:
     $ ssh -N -f -L 8080:localhost:8080 pipeline-prod

  d) Copy file to staging:
     $ scp fix.py pipeline-staging:/app/src/
     # OR using rsync (preferred for multiple files):
     $ rsync -avz fix.py pipeline-staging:/app/src/

  e) Tail remote log without interactive shell:
     $ ssh pipeline-prod 'tail -f /var/log/etl.log'
     # Or with timestamps visible:
     $ ssh pipeline-prod 'tail -f /var/log/etl.log | while read line; do echo "$(date): $line"; done'
""")


# ============================================================
# EXERCISE 6: Monitoring Scenario
# ============================================================

exercise(6, "Monitoring Scenario — High Memory and Slow Pipeline")

print("""
  It's 7:00 AM. Your daily pipeline normally finishes in 30 minutes.
  It's been running for 2.5 hours. The Slack alert says:
    "Warning: prod server memory usage at 92%"

  You have SSH access via: ssh pipeline-prod

  TASKS:
  ─────────────────────────────────────────────────────────────────────
  Write the EXACT sequence of commands you would run to:

  a) Get a quick overview of memory and disk usage.

  b) Find which process is using the most memory.

  c) Check the pipeline logs for clues — look for errors and also
     see what the pipeline is currently doing (the last 50 log lines).

  d) Check if the pipeline is making progress (is it stuck or slow?).
     How would you tell the difference between "stuck" and "slow"?

  e) You decide to kill the pipeline cleanly. How do you:
     1. Find the process ID (PID)
     2. Send a graceful termination signal
     3. Confirm it stopped

  f) After investigation, you find the pipeline is loading a 50GB CSV
     into a pandas DataFrame — that's the memory issue. What's the
     better approach? (Write the conceptual fix, not full code.)

  Write your answers before reading the answer below.
""")

answer_header()
print("""
  a) Quick overview:
     $ free -h               # RAM: total, used, free, available
     $ df -h                 # disk: all mounted filesystems
     # Or combine:
     $ free -h && echo && df -h

  b) Find memory-hungry process:
     $ ps aux --sort=-%mem | head -10
     # --sort=-%mem → descending memory usage, shows top 10

     $ top -o %MEM           # interactive top, sorted by memory

  c) Check pipeline logs:
     $ tail -50 /var/log/pipeline.log
     # Or for systemd:
     $ journalctl -u pipeline.service -n 50 --no-pager

     Look for:
       - ERROR or EXCEPTION lines (breaks/crashes)
       - Last timestamp (if it's old, the process may be stuck)
       - What stage it last logged (reading, transforming, writing?)

  d) Stuck vs slow:
     Stuck:  - logs show no new output (timestamp stopped advancing)
             - process CPU is near 0% (ps aux shows low %CPU)
             - no I/O activity: iotop shows no reads/writes

     Slow:   - logs ARE advancing (timestamp in recent seconds)
             - CPU is high (ps aux shows %CPU > 50%)
             - I/O is active (iotop shows disk or network reads)

     Commands:
     $ watch -n 2 'tail -5 /var/log/pipeline.log'  # is logging advancing?
     $ iotop -o -d 2                                # live I/O per process

  e) Kill the pipeline cleanly:
     1. Find PID:
        $ ps aux | grep pipeline.py
        # Or: $ pgrep -f pipeline.py

     2. Graceful termination (SIGTERM — gives app time to clean up):
        $ kill <PID>
        # Wait 10 seconds. If it doesn't stop:
        $ kill -9 <PID>   # SIGKILL — immediate, no cleanup

     3. Confirm stopped:
        $ ps aux | grep pipeline.py   # should be gone
        $ echo $?                     # or check exit code

  f) Fix for 50GB CSV into pandas:
     Instead of: df = pd.read_csv("giant_file.csv")  # loads all 50GB into RAM

     Approach 1 — chunked processing:
       for chunk in pd.read_csv("file.csv", chunksize=100_000):
           process(chunk)   # process 100k rows at a time, never loads full file

     Approach 2 — push work to the database:
       Use COPY or LOAD DATA to load the CSV directly into Postgres/Redshift.
       SQL databases are designed for this. pandas is not.

     Approach 3 — use Polars or DuckDB:
       Both handle larger-than-RAM datasets via streaming/lazy evaluation.
       DuckDB: SELECT * FROM 'giant_file.csv' WHERE ...  (streams it, no RAM)

     Approach 4 — load to S3 first, use Athena or Spark:
       For 50GB CSVs, you're in "big data" territory. Pandas on one server
       is the wrong tool. Athena queries S3 directly without loading to RAM.
""")


# ============================================================
# EXERCISE 7: Project Audit
# ============================================================

exercise(7, "Project Audit — Security and Best Practices")

print("""
  You join a team and review their data pipeline project.
  Here's what you find:

  FILE: config.py
  ─────────────────────────────────────────────────────────────────────
    AWS_ACCESS_KEY_ID     = "AKIAIOSFODNN7EXAMPLE"
    AWS_SECRET_ACCESS_KEY = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
    S3_BUCKET             = "prod-data-lake"
    DB_PASSWORD           = "super_secret_pass_123"
    DB_HOST               = "prod-db.company.com"

  FILE: pipeline.py (snippet)
  ─────────────────────────────────────────────────────────────────────
    import boto3
    from config import AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY

    s3 = boto3.client(
        "s3",
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    )

  OTHER OBSERVATIONS:
  ─────────────────────────────────────────────────────────────────────
  - No .gitignore exists in the project
  - No virtual environment (pip installs go to system Python)
  - The EC2 instance running this has AdministratorAccess IAM role
  - No Makefile (README has 12 manual steps to set up the project)
  - config.py is tracked in git (it was committed 6 months ago)

  TASKS:
  ─────────────────────────────────────────────────────────────────────
  a) List EVERY security and best-practice problem you can find.
     There are at least 8.

  b) Write the IMMEDIATE actions (do today, before anything else).

  c) Rewrite config.py and pipeline.py to use best practices.

  d) Write what the IAM role attached to the EC2 should look like
     (in plain English, not JSON).

  e) Write the .gitignore entries that should have been there from day 1.

  Write your answers before reading the answer below.
""")

answer_header()
print("""
  a) Problems found (there are 9):
     1. AWS credentials hardcoded in config.py — git history has them FOREVER
     2. DB password hardcoded in config.py — same git history problem
     3. config.py committed to git — now these credentials are in version history
        even if you delete the file (git log --all still shows them)
     4. No .gitignore — any file could accidentally be committed
     5. No virtual environment — package conflicts, non-reproducible installs
     6. AdministratorAccess IAM role — full AWS access if server is compromised
     7. boto3.client() takes explicit credentials — anti-pattern, bypasses IAM role
     8. No requirements.txt / requirements.in — nobody can reproduce the environment
     9. 12-step manual README setup — error-prone, inconsistent across team members

  b) Immediate actions (TODAY):
     1. Rotate the leaked credentials immediately:
        - Go to AWS Console → IAM → Access Keys → Delete/Deactivate AKIAIOSFODNN7...
        - Create new keys ONLY if absolutely needed (ideally: use IAM role instead)
     2. Remove secrets from git history:
        git filter-branch or BFG Repo-Cleaner to purge config.py from history
        (or if early in project: delete repo and recreate without the bad commit)
     3. Scan for other leaks: truffleHog or git-secrets on the full history
     4. Restrict the EC2 IAM role immediately (minimum: remove AdministratorAccess)

  c) Rewritten approach:

     config.py → DELETE IT. Replace with:

     # secrets.py
     import boto3, json

     def get_config() -> dict:
         \"\"\"Fetch all app config from Secrets Manager.\"\"\"
         client = boto3.client("secretsmanager", region_name="us-east-1")
         return json.loads(
             client.get_secret_value(SecretId="prod/pipeline/config")["SecretString"]
         )

     pipeline.py (new version):
     import boto3
     from secrets import get_config

     # boto3 uses IAM role automatically — NO explicit credentials needed
     s3 = boto3.client("s3")  # role provides credentials automatically

     # DB password fetched from Secrets Manager at runtime
     config = get_config()
     db_url = f"postgresql://{config['db_user']}:{config['db_password']}@{config['db_host']}/mydb"

  d) What the EC2 IAM role should allow (least privilege):
     - s3:GetObject, s3:PutObject, s3:ListBucket on ONLY 'prod-data-lake' bucket
     - secretsmanager:GetSecretValue on ONLY 'prod/pipeline/*' secrets
     - logs:CreateLogGroup, logs:CreateLogStream, logs:PutLogEvents
       (to write to CloudWatch Logs)
     - NOTHING ELSE
     - Definitely NOT: iam:*, ec2:*, rds:*, AdministratorAccess

  e) .gitignore (should have been committed on day 1):
     # Secrets and environment
     .env
     .env.*
     !.env.example
     config.py           ← explicitly block the bad file
     **/secrets.json
     *.pem
     *.key

     # Python
     .venv/
     __pycache__/
     *.pyc
     *.egg-info/
     dist/

     # Data
     *.csv
     *.parquet
     data/
     !data/.gitkeep
""")


# ============================================================
# SUMMARY
# ============================================================

section("WEEK 5 EXERCISES COMPLETE")

print("""
  You've worked through:

  Exercise 1: AWS CLI S3 — listing, uploading, syncing, presigned URLs, jq filtering
  Exercise 2: Secrets Manager — rewriting a pipeline to use secure credential storage
  Exercise 3: Environment Setup — pyenv + venv + requirements.in + .gitignore workflow
  Exercise 4: Makefile — a complete dbt project Makefile with variables and help target
  Exercise 5: SSH Config — ~/.ssh/config aliases and SSH tunneling for DB + Airflow
  Exercise 6: Monitoring — diagnosing high memory, finding stuck processes, fixing root cause
  Exercise 7: Project Audit — identifying and fixing 9 security and practice violations

  KEY TAKEAWAYS:
  ─────────────────────────────────────────────────────────────────────
  Security is not optional:
    Hardcoded credentials + committed to git = immediate, permanent breach.
    Use IAM roles on servers. Use Secrets Manager for runtime secrets.
    Use .gitignore from commit #1.

  Reproducibility is professionalism:
    A new teammate should run 'make install && make run' and have it work.
    Not wade through a 12-step README hoping their environment matches yours.

  Observability is reliability:
    If you can't tail the logs and see what's happening, you can't fix it fast.
    SSH tunneling > VPN for quick prod database access.
""")
