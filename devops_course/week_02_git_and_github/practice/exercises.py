"""
Week 2 Practice Setup — Git and GitHub
=========================================
Builds practice_repo/: a realistic git history (commits, a feature branch,
a hotfix branch, three tags) to run the exercises in exercises.md against.

This stays a .py file because it's genuinely doing something Python is for —
programmatically generating file content and a commit graph — not narrating
git commands you could just read.

Run:
    python3 exercises.py

Then open exercises.md and work through the 7 exercises yourself, in your
terminal, inside practice_repo/.
"""

import os
import subprocess
import shutil


def run(cmd, cwd=None):
    env = os.environ.copy()
    env["GIT_AUTHOR_NAME"] = "Data Engineer"
    env["GIT_AUTHOR_EMAIL"] = "de@example.com"
    env["GIT_COMMITTER_NAME"] = "Data Engineer"
    env["GIT_COMMITTER_EMAIL"] = "de@example.com"
    result = subprocess.run(
        cmd, shell=True, capture_output=True, text=True, cwd=cwd, env=env
    )
    return (result.stdout + result.stderr).strip()


def make_commit(msg, filename, content, cwd):
    """Write a file and commit it."""
    os.makedirs(os.path.dirname(os.path.join(cwd, filename)), exist_ok=True)
    with open(os.path.join(cwd, filename), "w") as f:
        f.write(content)
    run(f"git add {filename}", cwd=cwd)
    run(f'git commit -m "{msg}"', cwd=cwd)


def setup():
    """
    Create a practice git repo with a realistic history:
    multiple commits, branches, tags, and one deliberate conflict.
    """
    base = "./practice_repo"
    if os.path.exists(base):
        shutil.rmtree(base)
    os.makedirs(base)

    run("git init", cwd=base)
    run("git config user.email 'de@example.com'", cwd=base)
    run("git config user.name 'Data Engineer'", cwd=base)

    # ── Main branch history ──────────────────────────────────────────────

    make_commit(
        "Initialize data pipeline project",
        "pipeline.py",
        "# Data Pipeline\n\ndef run():\n    \"\"\"Main entry point.\"\"\"\n    extract()\n    transform()\n    load()\n",
        base,
    )

    make_commit(
        "Add configuration loader",
        "config.py",
        "import os\n\nDB_HOST = os.environ.get('DB_HOST', 'localhost')\nDB_PORT = int(os.environ.get('DB_PORT', 5432))\nS3_BUCKET = os.environ.get('S3_BUCKET', 'my-datalake')\n",
        base,
    )

    make_commit(
        "Add extract function with S3 source",
        "pipeline.py",
        "import boto3\nimport pandas as pd\n\ndef extract():\n    s3 = boto3.client('s3')\n    obj = s3.get_object(Bucket='my-bucket', Key='data/users.parquet')\n    return pd.read_parquet(obj['Body'])\n\ndef transform(df):\n    pass\n\ndef load(df, path):\n    pass\n\ndef run():\n    df = extract()\n    df = transform(df)\n    load(df, 's3://output/users/')\n",
        base,
    )

    make_commit(
        "Add null handling in transform",
        "pipeline.py",
        "import boto3\nimport pandas as pd\n\ndef extract():\n    s3 = boto3.client('s3')\n    obj = s3.get_object(Bucket='my-bucket', Key='data/users.parquet')\n    return pd.read_parquet(obj['Body'])\n\ndef transform(df):\n    df = df.dropna(subset=['user_id', 'email'])\n    df = df.drop_duplicates(subset=['user_id'])\n    return df\n\ndef load(df, path):\n    df.to_parquet(path, index=False)\n\ndef run():\n    df = extract()\n    df = transform(df)\n    load(df, 's3://output/users/')\n",
        base,
    )

    make_commit(
        "Add schema validation before load",
        "pipeline.py",
        "import boto3\nimport pandas as pd\n\nREQUIRED_COLUMNS = ['user_id', 'email', 'created_at']\n\ndef extract():\n    s3 = boto3.client('s3')\n    obj = s3.get_object(Bucket='my-bucket', Key='data/users.parquet')\n    return pd.read_parquet(obj['Body'])\n\ndef transform(df):\n    df = df.dropna(subset=['user_id', 'email'])\n    df = df.drop_duplicates(subset=['user_id'])\n    return df\n\ndef validate(df):\n    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]\n    if missing:\n        raise ValueError(f'Missing required columns: {missing}')\n\ndef load(df, path):\n    validate(df)\n    df.to_parquet(path, index=False)\n\ndef run():\n    df = extract()\n    df = transform(df)\n    load(df, 's3://output/users/')\n",
        base,
    )

    run("git tag v0.1.0", cwd=base)

    make_commit(
        "Add retry logic to S3 operations",
        "pipeline.py",
        "import boto3\nimport pandas as pd\nfrom botocore.exceptions import ClientError\nimport time\n\nREQUIRED_COLUMNS = ['user_id', 'email', 'created_at']\nMAX_RETRIES = 3\n\ndef extract(retries=MAX_RETRIES):\n    for attempt in range(retries):\n        try:\n            s3 = boto3.client('s3')\n            obj = s3.get_object(Bucket='my-bucket', Key='data/users.parquet')\n            return pd.read_parquet(obj['Body'])\n        except ClientError as e:\n            if attempt == retries - 1:\n                raise\n            time.sleep(2 ** attempt)\n\ndef transform(df):\n    df = df.dropna(subset=['user_id', 'email'])\n    df = df.drop_duplicates(subset=['user_id'])\n    return df\n\ndef validate(df):\n    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]\n    if missing:\n        raise ValueError(f'Missing required columns: {missing}')\n\ndef load(df, path):\n    validate(df)\n    df.to_parquet(path, index=False)\n\ndef run():\n    df = extract()\n    df = transform(df)\n    load(df, 's3://output/users/')\n",
        base,
    )

    make_commit(
        "Add orders pipeline module",
        "orders_pipeline.py",
        "import pandas as pd\n\ndef extract_orders(date):\n    return pd.DataFrame({'order_id': [], 'user_id': [], 'amount': []})\n\ndef transform_orders(df):\n    df = df[df['amount'] > 0]\n    return df\n\ndef load_orders(df, path):\n    df.to_parquet(path)\n",
        base,
    )

    # ── Feature branch: incremental load ──────────────────────────────────

    run("git checkout -b feature/add-incremental-load", cwd=base)

    make_commit(
        "Add watermark tracking for incremental loads",
        "watermark.py",
        "import json\nimport os\n\nWATERMARK_FILE = '.watermark.json'\n\ndef get_watermark(pipeline_name):\n    if not os.path.exists(WATERMARK_FILE):\n        return None\n    with open(WATERMARK_FILE) as f:\n        data = json.load(f)\n    return data.get(pipeline_name)\n\ndef set_watermark(pipeline_name, value):\n    data = {}\n    if os.path.exists(WATERMARK_FILE):\n        with open(WATERMARK_FILE) as f:\n            data = json.load(f)\n    data[pipeline_name] = value\n    with open(WATERMARK_FILE, 'w') as f:\n        json.dump(data, f, indent=2, default=str)\n",
        base,
    )

    make_commit(
        "Add incremental mode to extract function",
        "pipeline.py",
        "import boto3\nimport pandas as pd\nfrom botocore.exceptions import ClientError\nimport time\nfrom watermark import get_watermark, set_watermark\n\nREQUIRED_COLUMNS = ['user_id', 'email', 'created_at']\nMAX_RETRIES = 3\n\ndef extract(retries=MAX_RETRIES, incremental=False):\n    watermark = get_watermark('users') if incremental else None\n    for attempt in range(retries):\n        try:\n            s3 = boto3.client('s3')\n            obj = s3.get_object(Bucket='my-bucket', Key='data/users.parquet')\n            df = pd.read_parquet(obj['Body'])\n            if watermark:\n                df = df[df['updated_at'] > watermark]\n            return df\n        except ClientError as e:\n            if attempt == retries - 1:\n                raise\n            time.sleep(2 ** attempt)\n\ndef transform(df):\n    df = df.dropna(subset=['user_id', 'email'])\n    df = df.drop_duplicates(subset=['user_id'])\n    return df\n\ndef validate(df):\n    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]\n    if missing:\n        raise ValueError(f'Missing required columns: {missing}')\n\ndef load(df, path):\n    validate(df)\n    df.to_parquet(path, index=False)\n    set_watermark('users', df['updated_at'].max())\n\ndef run(incremental=False):\n    df = extract(incremental=incremental)\n    df = transform(df)\n    load(df, 's3://output/users/')\n",
        base,
    )

    run("git checkout main", cwd=base)

    # ── Hotfix branch (simulates a prod bug) ──────────────────────────────

    run("git checkout -b hotfix/fix-duplicate-key-crash", cwd=base)

    make_commit(
        "Fix crash when duplicate_keys parameter missing",
        "pipeline.py",
        "import boto3\nimport pandas as pd\nfrom botocore.exceptions import ClientError\nimport time\n\nREQUIRED_COLUMNS = ['user_id', 'email', 'created_at']\nMAX_RETRIES = 3\n\ndef extract(retries=MAX_RETRIES):\n    for attempt in range(retries):\n        try:\n            s3 = boto3.client('s3')\n            obj = s3.get_object(Bucket='my-bucket', Key='data/users.parquet')\n            return pd.read_parquet(obj['Body'])\n        except ClientError as e:\n            if attempt == retries - 1:\n                raise\n            time.sleep(2 ** attempt)\n\ndef transform(df, drop_duplicate_keys=True):\n    df = df.dropna(subset=['user_id', 'email'])\n    if drop_duplicate_keys:\n        df = df.drop_duplicates(subset=['user_id'])\n    return df\n\ndef validate(df):\n    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]\n    if missing:\n        raise ValueError(f'Missing required columns: {missing}')\n\ndef load(df, path):\n    validate(df)\n    df.to_parquet(path, index=False)\n\ndef run():\n    df = extract()\n    df = transform(df)\n    load(df, 's3://output/users/')\n",
        base,
    )

    run("git checkout main", cwd=base)
    run("git merge hotfix/fix-duplicate-key-crash --no-edit", cwd=base)
    run("git tag v0.1.1", cwd=base)

    # ── A few more main commits ──────────────────────────────────────────

    make_commit(
        "Add data quality checks module",
        "quality_checks.py",
        "def check_row_count(df, min_rows=1):\n    if len(df) < min_rows:\n        raise ValueError(f'Expected at least {min_rows} rows, got {len(df)}')\n\ndef check_null_rate(df, column, max_null_rate=0.05):\n    null_rate = df[column].isna().mean()\n    if null_rate > max_null_rate:\n        raise ValueError(f'{column} null rate {null_rate:.2%} exceeds threshold {max_null_rate:.2%}')\n\ndef check_uniqueness(df, column):\n    if df[column].duplicated().any():\n        raise ValueError(f'Column {column} contains duplicates')\n",
        base,
    )

    make_commit(
        "Add dbt project configuration",
        "dbt/dbt_project.yml",
        "name: data_pipelines\nversion: '1.0.0'\nconfig-version: 2\nmodel-paths: ['models']\nseed-paths: ['seeds']\n",
        base,
    )

    make_commit(
        "Add README with pipeline documentation",
        "README.md",
        "# Data Pipelines\n\n## Overview\nETL pipelines for users and orders data.\n\n## Pipelines\n- `pipeline.py` — Users ETL (supports incremental mode)\n- `orders_pipeline.py` — Orders ETL\n\n## Configuration\nSet environment variables or create a `.env` file (see `.env.example`).\n\n## Running\n```bash\npython3 pipeline.py\n```\n",
        base,
    )

    run("git tag v1.0.0", cwd=base)

    print("Setup complete. Practice repo created at ./practice_repo/")
    print()
    print("Git history:")
    result = subprocess.run(
        "git log --oneline --graph --all",
        shell=True, capture_output=True, text=True, cwd=base
    )
    for line in result.stdout.splitlines():
        print(f"  {line}")
    print()
    print("Branches:")
    result = subprocess.run(
        "git branch -a",
        shell=True, capture_output=True, text=True, cwd=base
    )
    for line in result.stdout.splitlines():
        print(f"  {line}")
    print()
    print("Now open exercises.md and work through the 7 exercises yourself.")


if __name__ == "__main__":
    setup()
