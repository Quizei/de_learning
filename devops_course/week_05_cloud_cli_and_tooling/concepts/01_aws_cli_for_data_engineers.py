"""
AWS CLI for Data Engineers
==========================
The AWS CLI is the command-line interface to AWS — every action you
can take in the AWS Console can be scripted, automated, and version-
controlled using the CLI. For data engineers, this is how you stop
clicking through S3 bucket UIs and start building reproducible pipelines.

This file covers:
- What the AWS CLI is and why you need it
- Installation and credentials setup
- S3 — the bread and butter (upload, download, sync, presign)
- --output and --query: making CLI output scriptable
- IAM: knowing who you are and what you can do
- Secrets Manager: the right way to store credentials
- SSM Parameter Store: cheaper config storage
- Useful one-liners for data teams

Run this file: python3 concepts/01_aws_cli_for_data_engineers.py
AWS CLI commands are printed (not executed) — no credentials needed.
Commands that don't need AWS (like 'which aws') are actually run.
"""

import subprocess
import sys


# ============================================================
# HELPERS
# ============================================================

def section(title):
    print()
    print("=" * 70)
    print(f"  {title}")
    print("=" * 70)


def show(cmd, note=""):
    """Run a command and print its output. For commands that work locally."""
    print(f"\n  $ {cmd}")
    if note:
        print(f"  # {note}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    output = (result.stdout + result.stderr).strip()
    if output:
        for line in output.splitlines()[:20]:
            print(f"    {line}")
    else:
        print("    (not found or no output)")


def demo(cmd, note=""):
    """Print an AWS CLI command with its purpose — does NOT execute it.

    Most AWS CLI commands require credentials and real resources.
    Printing them is the point: you read, understand, then run yourself.
    """
    print(f"\n  $ {cmd}")
    if note:
        print(f"  # {note}")


# ============================================================
# 1. WHAT THE AWS CLI IS
# ============================================================

section("1. WHAT THE AWS CLI IS")

print("""
  The AWS CLI is a program that talks to AWS APIs from your terminal.
  Anything you can click in the AWS Console, you can script with the CLI.

  Why this matters for data engineers:
    - Automate S3 syncs in pipeline scripts
    - Pull secrets from Secrets Manager at runtime (no hardcoded passwords)
    - Script infrastructure setup (buckets, IAM roles, parameter store)
    - Batch operations on thousands of S3 objects — impossible by hand
    - Combine with cron/Airflow/Makefiles for repeatable workflows

  Mental model:
    AWS Console  →  point-and-click GUI
    AWS CLI      →  same actions, but scriptable, composable, version-controllable
    boto3        →  same actions, but from Python code

  They all talk to the same underlying AWS API. The CLI is boto3's sibling.

  Every data engineering team uses the CLI. Learning it once pays forever.
""")


# ============================================================
# 2. INSTALLATION AND SETUP
# ============================================================

section("2. INSTALLATION AND SETUP")

print("""
  INSTALL:
  ─────────────────────────────────────────────────────────────────────
  macOS (Homebrew):
    brew install awscli

  pip (any OS):
    pip install awscli        # v1, older
    pip install awscli-v2     # v2, recommended

  Official installer (macOS):
    Download .pkg from https://awscli.amazonaws.com/AWSCLIV2.pkg
    Recommended for production machines — no Python dependency

  CONFIGURE:
  ─────────────────────────────────────────────────────────────────────
""")

demo(
    "aws configure",
    note="Interactive setup — prompts for 4 things:"
)

print("""
    AWS Access Key ID [None]: AKIAIOSFODNN7EXAMPLE
    AWS Secret Access Key [None]: wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
    Default region name [None]: us-east-1
    Default output format [None]: json

  This writes to two files:
    ~/.aws/credentials  — your access key and secret
    ~/.aws/config       — region, output format, and other settings
""")

demo(
    "aws configure --profile dev",
    note="Named profile — configure multiple AWS accounts"
)

print("""
  Named profiles let you switch between accounts:
    ~/.aws/credentials:
      [default]
      aws_access_key_id = AKIA...
      aws_secret_access_key = wJal...

      [dev]
      aws_access_key_id = AKIA...DEV
      aws_secret_access_key = wJal...DEV

      [prod]
      aws_access_key_id = AKIA...PROD
      aws_secret_access_key = wJal...PROD

  Use a profile: add --profile dev to any command
  Or set: export AWS_PROFILE=dev  (for current shell session)
""")

print("""
  CREDENTIAL SECURITY — READ THIS:
  ─────────────────────────────────────────────────────────────────────
  NEVER use your root AWS credentials.
    Root = full access to everything, including billing.
    One leaked key = your entire account compromised.

  NEVER hardcode credentials in code.
    print(secret_key)  — now they're in your git history forever.
    Even private repos get breached. GitHub bots scan for keys 24/7.

  DO: Create an IAM user with only the permissions the pipeline needs.
    S3-read-only pipeline → IAM policy: s3:GetObject on specific bucket.
    No more, no less. This is "principle of least privilege."

  EVEN BETTER: Use IAM roles + instance profiles (no long-lived keys):
    When your pipeline runs on EC2, ECS, or Lambda, attach an IAM ROLE.
    AWS automatically provides temporary credentials that rotate.
    No keys stored anywhere. Nothing to leak.

    boto3 automatically picks up role credentials — zero code changes.

  .env files vs credentials:
    .env files on your laptop: OK for development, NEVER commit to git.
    Hardcoded in code: NEVER.
    AWS Secrets Manager: use for production (covered in section 5).
""")


# ============================================================
# 3. CHECK IF INSTALLED (actually run these)
# ============================================================

section("3. VERIFY INSTALLATION (running these now)")

show("which aws", note="Where is the aws binary installed?")
show("aws --version", note="Which version is installed?")


# ============================================================
# 4. S3 — THE BREAD AND BUTTER
# ============================================================

section("4. S3 COMMANDS — The Data Engineer's Daily Driver")

print("""
  S3 (Simple Storage Service) is where data engineering happens.
  Raw data lands here. Processed data lives here. Exports go here.
  Parquet files, CSVs, JSON, logs — all in S3.

  Two interfaces:
    aws s3    — high-level: cp, mv, sync, ls, rm (user-friendly)
    aws s3api — low-level: direct API calls with full control

  Use aws s3 for daily work. Use aws s3api when you need metadata,
  ACLs, or operations that aws s3 doesn't expose.
""")

print("\n  --- LISTING ---")

demo(
    "aws s3 ls",
    note="List ALL your S3 buckets"
)

demo(
    "aws s3 ls s3://my-data-bucket/",
    note="List top-level contents of a bucket"
)

demo(
    "aws s3 ls s3://my-data-bucket/raw/2024/",
    note="List objects under a prefix (like a directory)"
)

demo(
    "aws s3 ls s3://my-data-bucket/ --recursive",
    note="List ALL objects in bucket including nested prefixes"
)

demo(
    "aws s3 ls s3://my-data-bucket/ --recursive --human-readable --summarize",
    note="List all objects + show total count and total size at the bottom"
)

print("\n  --- UPLOAD / DOWNLOAD ---")

demo(
    "aws s3 cp local_file.csv s3://my-data-bucket/raw/",
    note="Upload a single file to S3"
)

demo(
    "aws s3 cp s3://my-data-bucket/raw/data.csv ./local/",
    note="Download a single file from S3"
)

demo(
    "aws s3 cp s3://my-data-bucket/raw/ ./local_raw/ --recursive",
    note="Download an entire 'directory' (prefix) from S3"
)

print("\n  --- SYNC (the smart copy) ---")

demo(
    "aws s3 sync ./data/ s3://my-data-bucket/data/",
    note="Upload directory — only copies NEW or CHANGED files (skips identical)"
)

demo(
    "aws s3 sync s3://my-data-bucket/data/ ./local_data/",
    note="Download from S3 to local — only downloads new/changed files"
)

demo(
    'aws s3 sync ./data/ s3://my-data-bucket/ --exclude "*.tmp" --exclude ".DS_Store"',
    note="Sync but exclude temp files and macOS metadata files"
)

demo(
    "aws s3 sync s3://source-bucket/ s3://dest-bucket/",
    note="Copy between two S3 buckets directly (no local download needed)"
)

print("""
  sync vs cp:
    cp:   copies everything every time, even if unchanged
    sync: compares source and destination, only copies differences
    Use sync for large datasets — it's much faster on re-runs.
    Use cp for single files or when you always want a fresh copy.
""")

print("\n  --- DELETE ---")

demo(
    "aws s3 rm s3://my-data-bucket/raw/old_file.csv",
    note="Delete a single object"
)

demo(
    "aws s3 rm s3://my-data-bucket/tmp/ --recursive",
    note="Delete all objects under a prefix (like rm -rf for S3)"
)

print("\n  --- BUCKET MANAGEMENT ---")

demo(
    "aws s3 mb s3://my-new-data-bucket",
    note="Create a new bucket (mb = make bucket)"
)

demo(
    "aws s3 mb s3://my-new-data-bucket --region eu-west-1",
    note="Create bucket in a specific region (data residency compliance)"
)

print("\n  --- PRESIGNED URLs ---")

demo(
    "aws s3 presign s3://my-data-bucket/reports/q4_2024.csv --expires-in 3600",
    note="Generate a temporary public URL valid for 1 hour (3600 seconds)"
)

print("""
  Presigned URLs are crucial for sharing data without:
    - Making objects permanently public
    - Creating IAM users for external parties
    - Building a download API

  Common uses:
    - Share a report with a client for 24 hours
    - Provide a temporary download link in an email
    - Allow a vendor to upload to your bucket without an AWS account
    --expires-in 86400 = 24 hours, 604800 = 7 days (max)
""")

demo(
    "aws s3api get-object-attributes --bucket my-data-bucket --key raw/data.csv --object-attributes ETag,ObjectSize,StorageClass",
    note="Get metadata about an object WITHOUT downloading it"
)


# ============================================================
# 5. --OUTPUT AND --QUERY: SCRIPTING THE CLI
# ============================================================

section("5. --OUTPUT AND --QUERY — Making CLI Output Scriptable")

print("""
  By default, AWS CLI returns JSON. Three output formats exist:
    --output json   — default, good for piping to jq
    --output table  — human-readable grid, great for terminal browsing
    --output text   — tab-separated, good for shell scripts with awk/cut

  Example without --query (returns everything):
""")

demo(
    "aws s3api list-objects --bucket my-data-bucket",
    note="Returns a huge JSON blob with all object metadata"
)

print("""
  Example output (truncated):
    {
        "Contents": [
            {"Key": "raw/users.csv", "Size": 1024000, "LastModified": "2024-01-15T..."},
            {"Key": "raw/orders.csv", "Size": 5242880, "LastModified": "2024-01-16T..."},
            ...
        ]
    }

  --query lets you filter using JMESPath syntax:
""")

demo(
    "aws s3api list-objects --bucket my-data-bucket --query 'Contents[].{Key:Key,Size:Size}'",
    note="Extract only Key and Size fields from each object"
)

print("""
  Output with --query:
    [
        {"Key": "raw/users.csv", "Size": 1024000},
        {"Key": "raw/orders.csv", "Size": 5242880}
    ]

  --output text turns it into tab-separated values for shell scripts:
""")

demo(
    "aws s3api list-objects --bucket my-data-bucket --query 'Contents[].Key' --output text",
    note="Get just the keys as plain text, one per tab — pipe to shell commands"
)

print("""
  Real power move — combine with jq for complex filtering:
""")

demo(
    "aws s3api list-objects --bucket my-data-bucket | jq '.Contents[] | select(.Size > 1000000) | .Key'",
    note="Find all objects larger than 1MB using jq"
)

demo(
    "aws s3api list-objects --bucket my-data-bucket | jq '[.Contents[] | select(.Key | endswith(\".parquet\"))] | length'",
    note="Count how many .parquet files are in the bucket"
)

print("""
  Practical scripting pattern:
    # Get all keys as a list you can iterate over in bash
    FILES=$(aws s3api list-objects --bucket my-data-bucket \\
            --query 'Contents[].Key' --output text)
    for file in $FILES; do
        echo "Processing: $file"
    done
""")


# ============================================================
# 6. IAM — KNOWING WHO YOU ARE
# ============================================================

section("6. IAM — Knowing Who You Are and What You Can Do")

demo(
    "aws iam get-user",
    note="Who am I? Returns your IAM user name, ARN, and creation date"
)

print("""
  Sample output:
    {
        "User": {
            "UserName": "data-pipeline-user",
            "UserId": "AIDAIOSFODNN7EXAMPLE",
            "Arn": "arn:aws:iam::123456789012:user/data-pipeline-user",
            "CreateDate": "2024-01-01T00:00:00Z"
        }
    }
""")

demo(
    "aws iam list-attached-user-policies --user-name data-pipeline-user",
    note="What policies (permissions) does this user have?"
)

demo(
    "aws sts get-caller-identity",
    note="Who am I? Works for both IAM users AND assumed roles"
)

print("""
  aws sts get-caller-identity is the reliable "who am I" command.
  Works whether you're a real user or using a temporary role.

  Principle of least privilege — applied to data pipelines:

    BAD:  Give the pipeline IAM user AdministratorAccess
          (one leaked key = full account compromise)

    GOOD: Create a policy with exactly what the pipeline needs:
          {
            "Effect": "Allow",
            "Action": ["s3:GetObject", "s3:PutObject"],
            "Resource": "arn:aws:s3:::my-data-bucket/*"
          }

    BETTER: Use IAM roles on EC2/ECS/Lambda.
            No access keys. Credentials auto-rotate.
            Even if someone breaches the server, keys expire in ~1 hour.
""")


# ============================================================
# 7. SECRETS MANAGER
# ============================================================

section("7. SECRETS MANAGER — The Right Way to Store Credentials")

print("""
  Where NOT to put credentials:
    - Hardcoded in pipeline.py               → git history never forgets
    - .env file committed to git             → immediate breach
    - Printed in logs                        → logs are often public
    - Slack DMs to teammates                 → Slack stores everything
    - Email                                  → email is not encrypted

  Where to put credentials:
    - Development: .env file (NEVER committed, in .gitignore)
    - Production:  AWS Secrets Manager (or SSM Parameter Store)

  Secrets Manager is a managed vault:
    - Encrypted at rest (AES-256) and in transit
    - Fine-grained IAM access control
    - Automatic rotation for RDS passwords
    - Audit trail: who accessed what, when
    - Costs ~$0.40/month per secret — worth it
""")

demo(
    "aws secretsmanager get-secret-value --secret-id prod/db/postgres --query SecretString --output text",
    note="Fetch the secret value as plain text (no JSON wrapper)"
)

demo(
    "aws secretsmanager list-secrets",
    note="List all secrets in your account (names only, not values)"
)

demo(
    "aws secretsmanager create-secret --name prod/db/postgres --secret-string '{\"username\":\"etl_user\",\"password\":\"s3cr3t\"}'",
    note="Create a new secret (JSON string with multiple fields)"
)

print("""
  The boto3 equivalent — use this in your Python pipelines:
""")

print("""
  import boto3, json

  def get_db_credentials(secret_name: str, region: str = "us-east-1") -> dict:
      client = boto3.client("secretsmanager", region_name=region)
      response = client.get_secret_value(SecretId=secret_name)
      return json.loads(response["SecretString"])

  # At pipeline startup:
  creds = get_db_credentials("prod/db/postgres")
  db_url = f"postgresql://{creds['username']}:{creds['password']}@{creds['host']}/mydb"
""")

print("""
  .env file vs Secrets Manager — when to use each:

  .env file:
    - Local development only
    - Added to .gitignore (NEVER committed)
    - Quick to set up, easy to change
    - No cost
    - NOT suitable for production (file can be copied, printed)

  Secrets Manager:
    - Production environments
    - When multiple services need the same credentials
    - When you need rotation (e.g., RDS passwords rotate automatically)
    - When you need audit logs (compliance requirements)
    - When running on EC2/ECS/Lambda (no file system to store .env)

  Rule of thumb:
    dev laptop → .env file
    any server → Secrets Manager
""")


# ============================================================
# 8. SSM PARAMETER STORE
# ============================================================

section("8. SSM PARAMETER STORE — Cheaper Config Storage")

print("""
  SSM Parameter Store is like Secrets Manager but cheaper.

  When to use Parameter Store vs Secrets Manager:
    Parameter Store:  non-sensitive config (DB host, port, feature flags)
                      and less-sensitive secrets (API keys that are low-risk)
                      Standard tier: FREE. Up to 10,000 parameters.

    Secrets Manager:  passwords, connection strings, OAuth tokens
                      Automatic rotation capability
                      Full audit trail
                      $0.40/secret/month

  In practice: many teams use Parameter Store for everything except
  database passwords (which benefit from Secrets Manager's auto-rotation).
""")

demo(
    "aws ssm get-parameter --name /myapp/db_host",
    note="Get a plain text parameter value"
)

demo(
    "aws ssm get-parameter --name /myapp/db_password --with-decryption",
    note="Get a SecureString parameter (encrypted) — --with-decryption required"
)

demo(
    "aws ssm get-parameters-by-path --path /myapp/ --recursive --with-decryption",
    note="Get ALL parameters under a path prefix — great for loading app config"
)

demo(
    "aws ssm put-parameter --name /myapp/db_host --value 'prod-db.cluster.amazonaws.com' --type String",
    note="Create or update a plain text parameter"
)


# ============================================================
# 9. USEFUL ONE-LINERS
# ============================================================

section("9. USEFUL ONE-LINERS FOR DATA TEAMS")

print("""
  These are the commands you'll use every week:
""")

demo(
    "aws s3 ls s3://my-data-bucket/ --recursive | wc -l",
    note="Count total number of objects in a bucket"
)

demo(
    "aws s3 ls s3://my-data-bucket/ --recursive --human-readable --summarize | tail -2",
    note="Total size of a bucket (e.g., 'Total Size: 45.3 GiB, Total Objects: 12345')"
)

demo(
    "aws s3api list-objects-v2 --bucket my-data-bucket --query 'sort_by(Contents, &Size)[-5:]' --output table",
    note="Find the 5 largest files in a bucket"
)

demo(
    "aws s3 ls s3://my-data-bucket/raw/ --recursive | grep '2024-01-15'",
    note="Find all files modified on a specific date"
)

demo(
    "aws s3 ls s3://my-data-bucket/raw/ --recursive | grep '.parquet' | awk '{print $3}' | paste -sd+ | bc",
    note="Sum total bytes of all .parquet files in a prefix"
)

demo(
    "aws s3api list-objects-v2 --bucket my-data-bucket --prefix 'raw/' --query 'Contents[?contains(Key, `.parquet`)].Key' --output text",
    note="List only .parquet files in a prefix using --query filter"
)

demo(
    "aws s3 sync ./data/ s3://my-data-bucket/ --dryrun",
    note="Preview what sync WOULD upload without actually uploading"
)

demo(
    "for BUCKET in $(aws s3 ls | awk '{print $3}'); do echo \"$BUCKET:\"; aws s3 ls s3://$BUCKET/ --recursive --summarize 2>/dev/null | tail -1; done",
    note="List all your buckets with their total sizes"
)


# ============================================================
# QUICK REFERENCE
# ============================================================

print()
print("=" * 70)
print("  QUICK REFERENCE — AWS CLI for Data Engineers")
print("=" * 70)
print("""
  SETUP:
    aws configure                   interactive credentials setup
    aws configure --profile dev     named profile for dev account
    aws sts get-caller-identity     "who am I?" — user or role

  S3 — LISTING:
    aws s3 ls                       list all your buckets
    aws s3 ls s3://bucket/          list bucket contents
    aws s3 ls s3://bucket/ --recursive  list all objects recursively
    aws s3 ls s3://bucket/ --recursive --human-readable --summarize

  S3 — TRANSFER:
    aws s3 cp file.csv s3://bucket/prefix/   upload
    aws s3 cp s3://bucket/file.csv ./        download
    aws s3 sync ./local/ s3://bucket/        sync local to S3
    aws s3 sync s3://bucket/ ./local/        sync S3 to local
    aws s3 sync ... --exclude "*.tmp"        sync with exclusions
    aws s3 sync ... --dryrun                 preview without running

  S3 — OTHER:
    aws s3 rm s3://bucket/file.csv            delete object
    aws s3 rm s3://bucket/prefix/ --recursive delete all under prefix
    aws s3 mb s3://new-bucket                 create bucket
    aws s3 presign s3://bucket/file --expires-in 3600

  SCRIPTING:
    --output json|table|text        control output format
    --query 'Contents[].Key'        JMESPath filter
    | jq '.field'                   complex JSON processing

  SECRETS:
    aws secretsmanager get-secret-value --secret-id NAME --query SecretString --output text
    aws ssm get-parameter --name /app/key --with-decryption

  PROFILE SWITCHING:
    --profile dev                   use named profile for one command
    export AWS_PROFILE=prod         set profile for current shell
""")
