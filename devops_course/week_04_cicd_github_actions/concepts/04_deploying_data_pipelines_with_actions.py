"""
Deploying Data Pipelines with GitHub Actions
=============================================
"Deploy with confidence — every time, the same way."

Getting tests to pass is CI. Getting working code to production automatically
is CD. This file covers the deployment side: how data pipelines actually
get shipped to production using GitHub Actions.

This file covers:
- The four deployment patterns for data pipelines
- Building and pushing Docker images on merge to main
- Environment-based deployment (dev → staging → prod)
- Secrets in deployment workflows
- Notifications on failure (Slack webhook pattern)
- Reusable workflows with workflow_call
- A complete deploy.yml: build → push → notify

Run this file: python3 concepts/04_deploying_data_pipelines_with_actions.py
Deployment workflows are printed and explained — they run in GitHub's cloud.
"""

# ============================================================
# HELPERS
# ============================================================

def section(title):
    print()
    print("=" * 70)
    print(f"  {title}")
    print("=" * 70)


def explain_yaml(yaml_str, notes=""):
    print()
    print("  " + "-" * 66)
    for line in yaml_str.strip().splitlines():
        print(f"  {line}")
    print("  " + "-" * 66)
    if notes:
        print()
        for note_line in notes.strip().splitlines():
            print(f"  {note_line}")


# ============================================================
# 1. THE FOUR DEPLOYMENT PATTERNS FOR DATA PIPELINES
# ============================================================

section("1. THE FOUR DEPLOYMENT PATTERNS FOR DATA PIPELINES")

print("""
  Data pipelines are deployed differently depending on the platform.
  Here are the four most common patterns in the industry.

  ┌─────────────────────────────────────────────────────────────────┐
  │  Pattern              Platform               Deployment Action    │
  ├─────────────────────────────────────────────────────────────────┤
  │  1. Airflow DAGs      Managed/self-hosted    rsync/copy .py files │
  │  2. dbt models        Snowflake/BigQuery      dbt run, dbt test   │
  │  3. Docker pipeline   ECS, Cloud Run, K8s    build + push image   │
  │  4. Lambda / Cloud Fn Serverless              zip + upload         │
  └─────────────────────────────────────────────────────────────────┘
""")

print("\n  --- PATTERN 1: Airflow DAG Deployment ---")

airflow_deploy_yaml = """
# Deploy DAG files to Airflow on merge to main
name: Deploy Airflow DAGs

on:
  push:
    branches: [main]
    paths:
      - 'dags/**'               # Only when DAG files change

jobs:
  validate-dags:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: {python-version: '3.11'}
      - run: pip install apache-airflow
      - name: Validate DAG syntax
        run: |
          python -c "
          import importlib.util, glob
          for dag_file in glob.glob('dags/*.py'):
              spec = importlib.util.spec_from_file_location('dag', dag_file)
              mod = importlib.util.module_from_spec(spec)
              spec.loader.exec_module(mod)
              print(f'OK: {dag_file}')
          "

  deploy-dags:
    runs-on: ubuntu-latest
    needs: [validate-dags]
    steps:
      - uses: actions/checkout@v4
      - name: Copy DAGs to Airflow server
        env:
          AIRFLOW_HOST: ${{ secrets.AIRFLOW_HOST }}
          AIRFLOW_SSH_KEY: ${{ secrets.AIRFLOW_SSH_KEY }}
        run: |
          echo "$AIRFLOW_SSH_KEY" > /tmp/deploy_key
          chmod 600 /tmp/deploy_key
          rsync -avz -e "ssh -i /tmp/deploy_key -o StrictHostKeyChecking=no" \\
            dags/ \\
            airflow@$AIRFLOW_HOST:/opt/airflow/dags/
"""

explain_yaml(airflow_deploy_yaml, """
  AIRFLOW DEPLOYMENT STRATEGY:
    DAG files are Python files. Airflow scans its dags/ directory.
    The deployment is simple: copy .py files to the Airflow server.
    rsync is perfect: only transfers changed files, fast.

  CRITICAL STEP: validate-dags
    Import every DAG file in Python before deploying.
    A syntax error in a DAG breaks ALL DAGs in that file.
    Python -c import catches it before it reaches production Airflow.

  For managed Airflow (Cloud Composer, MWAA, Astro):
    - Cloud Composer: use gcloud storage cp to copy to GCS bucket
    - MWAA: use aws s3 sync to copy to S3 bucket
    - Astro: use astro deploy CLI
""")

print("\n  --- PATTERN 2: dbt Deployment ---")

dbt_deploy_yaml = """
name: Deploy dbt Models

on:
  push:
    branches: [main]
    paths:
      - 'dbt/**'

jobs:
  dbt-deploy:
    runs-on: ubuntu-latest
    env:
      DBT_PROFILES_DIR: ./dbt
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with: {python-version: '3.11'}

      - run: pip install dbt-snowflake

      - name: Configure dbt profile
        env:
          SNOWFLAKE_ACCOUNT: ${{ secrets.SNOWFLAKE_ACCOUNT }}
          SNOWFLAKE_USER: ${{ secrets.SNOWFLAKE_USER }}
          SNOWFLAKE_PASSWORD: ${{ secrets.SNOWFLAKE_PASSWORD }}
        run: |
          mkdir -p ~/.dbt
          cat > ~/.dbt/profiles.yml << EOF
          my_project:
            target: prod
            outputs:
              prod:
                type: snowflake
                account: $SNOWFLAKE_ACCOUNT
                user: $SNOWFLAKE_USER
                password: $SNOWFLAKE_PASSWORD
                database: ANALYTICS
                schema: MARTS
                warehouse: TRANSFORMING
          EOF

      - name: dbt deps
        run: dbt deps --project-dir dbt/

      - name: dbt build (test + run modified models)
        run: dbt build --project-dir dbt/ --select state:modified+
        # state:modified+ runs only changed models and their downstream deps
        # Without this: runs ALL models on every push (expensive in Snowflake)
"""

explain_yaml(dbt_deploy_yaml, """
  dbt DEPLOYMENT KEY CONCEPTS:

  state:modified+
    "Run only models I changed, plus everything downstream."
    Without this selector: every push runs ALL 500 dbt models = expensive.
    With it: if you changed 2 models, only 2+downstream run = cheap + fast.
    Requires: dbt artifacts from the previous production run (manifest.json).

  dbt build vs dbt run + dbt test:
    dbt build = dbt run + dbt test combined, in the right order.
    Use dbt build in CI/CD — it's the canonical production command.

  Profile configuration:
    dbt profiles.yml contains connection credentials.
    NEVER commit profiles.yml with real credentials.
    Generate it in the CI step from secrets.

  For dbt Cloud users:
    Use the dbt Cloud API to trigger a job instead of running dbt CLI directly.
    actions/setup-python + curl to the dbt Cloud REST API.
""")

print("\n  --- PATTERN 3: Docker Pipeline Deployment ---")

print("""
  Most common for data pipelines that run as containerized jobs.
  Examples: Spark jobs, custom Python ETL, ML pipelines.
  Target: AWS ECS, Google Cloud Run, Kubernetes.

  The workflow: build image → tag with git SHA → push to registry → update deployment.
  See Section 3 for the complete Docker build+push workflow.
""")

print("\n  --- PATTERN 4: Lambda / Cloud Function ---")

lambda_deploy_yaml = """
name: Deploy Lambda Function

on:
  push:
    branches: [main]
    paths:
      - 'lambda/**'

jobs:
  deploy-lambda:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with: {python-version: '3.11'}

      - name: Install dependencies into package
        run: |
          mkdir -p lambda_package
          pip install -r lambda/requirements.txt -t lambda_package/
          cp -r lambda/*.py lambda_package/

      - name: Zip the package
        run: |
          cd lambda_package && zip -r ../lambda.zip . && cd ..

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: us-east-1

      - name: Deploy to Lambda
        run: |
          aws lambda update-function-code \\
            --function-name my-etl-function \\
            --zip-file fileb://lambda.zip
"""

explain_yaml(lambda_deploy_yaml, """
  LAMBDA DEPLOYMENT STEPS:
    1. Install dependencies into a flat directory (no virtual env).
    2. Copy your .py files into that directory.
    3. Zip everything.
    4. Use aws lambda update-function-code to push the zip.

  WHY PIP INSTALL -t lambda_package/:
    Lambda needs all dependencies in the same zip as your code.
    -t target_dir installs packages INTO that directory (not your Python env).

  AWS OIDC (recommended over static keys):
    Instead of AWS_ACCESS_KEY_ID in secrets, use OpenID Connect:
    - No long-lived keys stored in GitHub
    - GitHub gets short-lived tokens from AWS STS
    - More secure, especially for public repos
    See: aws-actions/configure-aws-credentials@v4 with role-to-assume:
""")


# ============================================================
# 2. DOCKER BUILD AND PUSH WORKFLOW
# ============================================================

section("2. DOCKER BUILD AND PUSH — THE CORE DEPLOYMENT PATTERN")

print("""
  Building a Docker image and pushing it to a registry is the
  most common deployment step for Python data pipelines.
  The image is the deployable artifact.
""")

docker_build_yaml = """
jobs:
  build-and-push:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3
        # Enables BuildKit: faster builds, layer caching, multi-platform

      - name: Log in to Docker Hub
        uses: docker/login-action@v3
        with:
          username: ${{ secrets.DOCKERHUB_USERNAME }}
          password: ${{ secrets.DOCKERHUB_TOKEN }}
          # DOCKERHUB_TOKEN: generate at hub.docker.com > Account Settings > Security

      - name: Extract metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: myorg/my-pipeline
          tags: |
            type=sha,prefix=                    # full git SHA tag
            type=ref,event=branch               # branch name tag
            type=semver,pattern={{version}}     # v1.2.3 tag (if you push a tag)

      - name: Build and push
        uses: docker/build-push-action@v5
        with:
          context: .
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha              # GitHub Actions cache for layers
          cache-to: type=gha,mode=max
"""

explain_yaml(docker_build_yaml, """
  STEP BREAKDOWN:

  docker/setup-buildx-action@v3
    Enables Docker BuildKit — the modern build system.
    Required before docker/build-push-action.
    Enables layer caching in GitHub Actions cache (huge speedup).

  docker/login-action@v3
    Authenticates to Docker Hub using secrets.
    DOCKERHUB_TOKEN is a Docker Hub Access Token (not your password).
    For ECR: use aws-actions/amazon-ecr-login@v2 instead.
    For GCR: use google-github-actions/auth@v2 + docker/login-action with gcr.io.

  docker/metadata-action@v5
    Generates tags and labels automatically.
    type=sha: tags the image with the git commit SHA
    This is the key practice: every image is traceable to a git commit.

  IMAGE TAGGING STRATEGY:
    :latest        → always the most recent image. AVOID relying on this.
                     If you pin :latest, you have no idea which code is running.
    :abc123def     → git SHA tag. EXACT. You know exactly what code is inside.
    :main          → branch name. Useful for pulling latest from a branch.
    :v1.2.3        → semantic version tag. Best for production pinning.

  RECOMMENDATION:
    Always tag with git SHA in your deployments.
    In your ECS task definition or Kubernetes manifest, pin to the SHA tag.
    Rolling back = deploy the previous SHA tag. Instant and traceable.

  cache-from: type=gha / cache-to: type=gha,mode=max
    GitHub Actions layer cache for Docker builds.
    Unchanged layers are restored from cache → much faster rebuilds.
    Without caching: every build reinstalls all pip packages in the image.
    With caching: only changed layers rebuild.
""")


# ============================================================
# 3. ENVIRONMENT-BASED DEPLOYMENT
# ============================================================

section("3. ENVIRONMENT-BASED DEPLOYMENT — DEV TO STAGING TO PROD")

print("""
  A mature deployment pipeline has multiple environments.
  Code flows through them in order:

  feature branch → dev environment (optional)
  main branch    → staging environment (automatically)
  main branch    → prod environment (after human approval OR automatically)
""")

environments_yaml = """
jobs:
  deploy-staging:
    runs-on: ubuntu-latest
    environment: staging          # GitHub Environment name
    if: github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v4
      - name: Deploy to staging
        env:
          DB_URL: ${{ secrets.STAGING_DB_URL }}   # Environment-scoped secret
        run: ./scripts/deploy.sh staging

  deploy-prod:
    runs-on: ubuntu-latest
    environment: production       # Different environment — different secrets
    needs: [deploy-staging]       # Wait for staging to succeed
    if: github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v4
      - name: Deploy to production
        env:
          DB_URL: ${{ secrets.PROD_DB_URL }}       # Production secrets
        run: ./scripts/deploy.sh production
"""

explain_yaml(environments_yaml, """
  GITHUB ENVIRONMENTS:

  Set up in: repo Settings → Environments → New environment

  What environments give you:
    1. Environment-scoped secrets
       secrets.STAGING_DB_URL is ONLY available in jobs with environment: staging
       secrets.PROD_DB_URL is ONLY available in jobs with environment: production
       Even if someone reads the CI YAML, they can't access prod secrets from staging jobs.

    2. Protection rules
       Add required reviewers: a human must approve before deploy-prod runs.
       This enforces "four eyes" for production deployments.
       The workflow PAUSES and waits for approval in the GitHub UI.

    3. Deployment history
       Every deployment is recorded with who deployed, when, from which commit.
       You can see a timeline: "deployed abc123 at 14:30, deployed def456 at 16:00"

    4. Deployment branch restrictions
       Only allow deployments from main branch (not feature branches).

  PATTERN: DEPLOY TO STAGING → WAIT → DEPLOY TO PROD
    deploy-staging runs automatically on main push.
    deploy-prod has "required reviewers" in GitHub Environments.
    After staging deploy, a reviewer in GitHub UI clicks "Approve".
    Then deploy-prod runs automatically.
    This is Continuous Delivery: always deployable, human approves prod.
""")


# ============================================================
# 4. SECRETS IN DEPLOYMENT
# ============================================================

section("4. SECRETS IN DEPLOYMENT — THE RIGHT WAY")

print("""
  Secrets are the most sensitive part of any CI/CD pipeline.
  Getting this wrong means credentials leak. Here is the right approach.
""")

secrets_yaml = """
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      # CORRECT: pass secret as env var, use env var in script
      - name: Deploy with credentials
        env:
          AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
          AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          DATABASE_URL: ${{ secrets.PROD_DATABASE_URL }}
        run: |
          # Use env vars in scripts — GitHub masks them in logs
          aws s3 sync output/ s3://my-pipeline-output/
          python deploy_pipeline.py  # reads DATABASE_URL from environment

      # WRONG: directly embed secret in run command (visible in YAML, partial masking)
      # - name: BAD EXAMPLE
      #   run: python deploy.py --db-url ${{ secrets.DATABASE_URL }}
      #   # AVOID: appears as plaintext in workflow YAML and may leak in subcommands
"""

explain_yaml(secrets_yaml, """
  SECRET RULES:

  RULE 1: Never put ${{ secrets.X }} directly in a run: command.
    It appears as plaintext in the YAML file.
    GitHub masks the VALUE in logs but the YAML is public in public repos.
    INSTEAD: assign to env var, use env var in your Python/bash script.

  RULE 2: Never echo a secret.
    echo ${{ secrets.PASSWORD }}   → shows *** in logs (masked)
    echo $PASSWORD                 → if PASSWORD contains * or special chars,
                                     parts might not be masked. Don't risk it.

  RULE 3: Never write secrets to files that get uploaded as artifacts.
    upload-artifact saves files that anyone with repo access can download.
    If your script writes DATABASE_URL to a config file, don't upload that file.

  RULE 4: Use environment secrets for prod credentials.
    Repo secrets: available to ALL jobs. Anyone who can write a workflow can use them.
    Environment secrets: ONLY available when environment: production is set.
    Production DB URL should be an environment secret, not a repo secret.

  RULE 5: Rotate secrets regularly.
    Use fine-grained tokens (expire in 90 days) not long-lived ones.
    GitHub personal access tokens should have minimum required permissions.

  GITHUB AUTOMATICALLY MASKS:
    GitHub scans log output and replaces exact matches of secret values with ***.
    This is a safety net, not a substitute for following the rules above.
    It catches: "Password: abc123" → "Password: ***"
    It misses: base64-encoded secrets, split across lines, etc.
""")


# ============================================================
# 5. NOTIFICATIONS ON FAILURE
# ============================================================

section("5. NOTIFICATIONS ON FAILURE — SLACK WEBHOOK PATTERN")

print("""
  When a prod deployment fails, the team needs to know immediately.
  GitHub has built-in email notifications, but Slack is standard.
  The pattern: a final step that only runs if: failure().
""")

notifications_yaml = """
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Build Docker image
        run: docker build -t myapp:${{ github.sha }} .

      - name: Push to registry
        run: docker push myapp:${{ github.sha }}

      - name: Update ECS task
        run: aws ecs update-service --cluster prod --service my-pipeline --force-new-deployment

      # Notification steps — always at the end
      - name: Notify Slack on success
        if: success()
        run: |
          curl -X POST -H 'Content-type: application/json' \\
            --data '{
              "text": "Deployment SUCCEEDED",
              "attachments": [{
                "color": "good",
                "fields": [
                  {"title": "Repo", "value": "${{ github.repository }}", "short": true},
                  {"title": "Commit", "value": "${{ github.sha }}", "short": true},
                  {"title": "Author", "value": "${{ github.actor }}", "short": true}
                ]
              }]
            }' \\
            ${{ secrets.SLACK_WEBHOOK_URL }}

      - name: Notify Slack on failure
        if: failure()
        run: |
          curl -X POST -H 'Content-type: application/json' \\
            --data '{
              "text": "Deployment FAILED — immediate attention needed",
              "attachments": [{
                "color": "danger",
                "fields": [
                  {"title": "Repo", "value": "${{ github.repository }}", "short": true},
                  {"title": "Commit", "value": "${{ github.sha }}", "short": true},
                  {"title": "Actor", "value": "${{ github.actor }}", "short": true},
                  {"title": "Run URL", "value": "${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}", "short": false}
                ]
              }]
            }' \\
            ${{ secrets.SLACK_WEBHOOK_URL }}
"""

explain_yaml(notifications_yaml, """
  SLACK NOTIFICATION SETUP:
    1. Go to api.slack.com/apps → Create New App → From Scratch
    2. Add "Incoming Webhooks" feature → Activate it
    3. Add New Webhook to Workspace → Select channel
    4. Copy the Webhook URL (https://hooks.slack.com/services/...)
    5. Add to GitHub: Settings → Secrets → SLACK_WEBHOOK_URL

  if: success() vs if: failure() vs if: always():
    success()  → only run when ALL previous steps passed
    failure()  → only run when ANY previous step failed
    always()   → run regardless (use for guaranteed cleanup steps)

  Run URL in the failure message:
    ${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}
    This creates a clickable link directly to the failing workflow run.
    The on-call engineer clicks the Slack message → goes straight to the failure log.

  ALTERNATIVE: slack-github-action (Marketplace):
    uses: slackapi/slack-github-action@v1.25.0
    with:
      payload: |
        {"text": "Deployment ${{ job.status }}"}
    env:
      SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_URL }}
""")


# ============================================================
# 6. REUSABLE WORKFLOWS
# ============================================================

section("6. REUSABLE WORKFLOWS — SHARE CI LOGIC ACROSS REPOS")

print("""
  If your organisation has 20 data pipeline repos, you don't want to
  copy-paste the same CI YAML into every one.
  Reusable workflows let you define CI once and call it from anywhere.
""")

reusable_caller_yaml = """
# In: org/data-pipelines-standards/.github/workflows/python-ci.yml
name: Reusable Python CI

on:
  workflow_call:                    # This is what makes it callable
    inputs:
      python-version:
        required: false
        type: string
        default: '3.11'
      coverage-threshold:
        required: false
        type: number
        default: 70
    secrets:
      SLACK_WEBHOOK_URL:
        required: false

jobs:
  ci:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ inputs.python-version }}
      - run: pip install -r requirements-dev.txt
      - run: ruff check . && black --check .
      - run: pytest --cov=src --cov-fail-under=${{ inputs.coverage-threshold }}
"""

explain_yaml(reusable_caller_yaml, """
  CALLING THE REUSABLE WORKFLOW FROM ANOTHER REPO:

  # In: my-pipeline-repo/.github/workflows/ci.yml
  jobs:
    call-shared-ci:
      uses: org/data-pipelines-standards/.github/workflows/python-ci.yml@main
      with:
        python-version: '3.12'
        coverage-threshold: 80
      secrets:
        SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_URL }}

  HOW IT WORKS:
    - The "caller" repo invokes the reusable workflow like a function call.
    - inputs: are named parameters (like function arguments).
    - secrets: propagated explicitly (secrets don't auto-inherit for security).
    - The reusable workflow runs in the CONTEXT of the caller repo.

  USE CASES FOR DATA TEAMS:
    - org-wide linting standards (same ruff config everywhere)
    - standard dbt deployment workflow called from all dbt repos
    - shared Slack notification templates
    - standard Docker build-push pattern

  BENEFIT: When you update the reusable workflow, ALL repos get the update.
  No need to copy-paste bugfixes to 20 repos.
""")


# ============================================================
# 7. COMPLETE DEPLOY.YML WORKFLOW
# ============================================================

section("7. COMPLETE DEPLOY.YML — BUILD, PUSH, NOTIFY")

print("""
  Here is the complete deploy.yml that ties everything together.
  Triggers only on main push, builds and pushes a Docker image,
  then notifies Slack on success or failure.
""")

complete_deploy_yaml = """
# .github/workflows/deploy.yml
name: Deploy Pipeline

on:
  push:
    branches: [main]              # Only deploy on main branch merges
    paths:
      - '**.py'
      - 'Dockerfile'
      - 'requirements*.txt'

jobs:
  build-and-push:
    name: Build and Push Docker Image
    runs-on: ubuntu-latest
    environment: production       # Uses production-scoped secrets

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Log in to Docker Hub
        uses: docker/login-action@v3
        with:
          username: ${{ secrets.DOCKERHUB_USERNAME }}
          password: ${{ secrets.DOCKERHUB_TOKEN }}

      - name: Extract metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ secrets.DOCKERHUB_USERNAME }}/my-pipeline
          tags: |
            type=sha,prefix=             # Tag: full git SHA
            type=raw,value=latest        # Tag: latest (also update)

      - name: Build and push Docker image
        uses: docker/build-push-action@v5
        with:
          context: .
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

      - name: Output image digest
        run: echo "Image pushed with tags: ${{ steps.meta.outputs.tags }}"

      # ── NOTIFICATIONS ─────────────────────────────────────────

      - name: Notify Slack on success
        if: success()
        run: |
          curl -s -X POST -H 'Content-type: application/json' \\
            --data '{
              "text": ":white_check_mark: Deploy succeeded: `${{ github.repository }}` @ `${{ github.sha }}`",
              "blocks": [{
                "type": "section",
                "text": {
                  "type": "mrkdwn",
                  "text": "*Deploy succeeded* :rocket:\\n*Repo:* ${{ github.repository }}\\n*SHA:* `${{ github.sha }}`\\n*By:* ${{ github.actor }}"
                }
              }]
            }' \\
            ${{ secrets.SLACK_WEBHOOK_URL }}

      - name: Notify Slack on failure
        if: failure()
        run: |
          curl -s -X POST -H 'Content-type: application/json' \\
            --data '{
              "text": ":x: Deploy FAILED: `${{ github.repository }}` @ `${{ github.sha }}`",
              "blocks": [{
                "type": "section",
                "text": {
                  "type": "mrkdwn",
                  "text": "*Deploy FAILED* :fire:\\n*Repo:* ${{ github.repository }}\\n*SHA:* `${{ github.sha }}`\\n*By:* ${{ github.actor }}\\n*Logs:* ${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}"
                }
              }]
            }' \\
            ${{ secrets.SLACK_WEBHOOK_URL }}
"""

explain_yaml(complete_deploy_yaml, """
  WHY paths: FILTER ON DEPLOY TOO:
    If someone edits README.md, there is no need to rebuild the Docker image.
    The paths filter prevents unnecessary deploys from documentation changes.
    Include Dockerfile and requirements*.txt — these change the image.

  ENVIRONMENT: production
    Scopes secrets to the production environment.
    If you have required reviewers configured, the job PAUSES here for approval.
    Without approval: the steps never run.

  TAGGING WITH SHA + LATEST:
    type=sha: tags as the full commit hash (40 characters).
    type=raw,value=latest: also tags as :latest (for convenience).
    Production deployments should ALWAYS reference the SHA tag.
    :latest is just a convenience pointer for humans.

  NOTIFICATION FLOW:
    Build succeeds → success() step sends green Slack message.
    Build fails → failure() step sends red Slack message with log URL.
    Both steps always run (success/failure are mutually exclusive).

  SECRETS NEEDED FOR THIS WORKFLOW:
    DOCKERHUB_USERNAME     your Docker Hub username
    DOCKERHUB_TOKEN        Docker Hub access token (Settings > Security)
    SLACK_WEBHOOK_URL      Slack incoming webhook URL

  TO ACTUALLY DEPLOY (not just push image):
    Add a step after the push that updates your deployment target:
    ECS:        aws ecs update-service --force-new-deployment
    Cloud Run:  gcloud run deploy --image gcr.io/project/image:sha
    Kubernetes: kubectl set image deployment/pipeline pipeline=image:sha
""")


# ============================================================
# QUICK REFERENCE
# ============================================================

print()
print("=" * 70)
print("  QUICK REFERENCE — Deploying Data Pipelines with Actions")
print("=" * 70)
print("""
  FOUR DEPLOYMENT PATTERNS:
    1. Airflow DAGs   → validate syntax → rsync/s3 sync .py files
    2. dbt models     → dbt deps + dbt build --select state:modified+
    3. Docker image   → build → push to registry → update ECS/Cloud Run/K8s
    4. Lambda         → pip install -t pkg/ → zip → aws lambda update-function-code

  IMAGE TAGGING STRATEGY:
    :sha (git SHA)    precise, traceable — use for prod deployments
    :latest           convenience only — don't pin to this in prod
    :v1.2.3           semantic version — best for public containers

  ENVIRONMENT SECRETS:
    environment: production       scopes secrets to production
    secrets.PROD_DB_URL           only available in production environment jobs
    secrets.STAGING_DB_URL        only available in staging environment jobs

  NOTIFICATION PATTERN:
    if: success()     → green Slack message
    if: failure()     → red Slack message with run URL
    ${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}
    → direct link to failing run in Slack message

  REUSABLE WORKFLOW:
    on: workflow_call:              makes the workflow callable
    uses: org/repo/.github/workflows/ci.yml@main    calls it

  DEPLOY.YML TRIGGER (only on main):
    on:
      push:
        branches: [main]
        paths: ['**.py', 'Dockerfile', 'requirements*.txt']

  REQUIRED SECRETS FOR DOCKER DEPLOY:
    DOCKERHUB_USERNAME, DOCKERHUB_TOKEN, SLACK_WEBHOOK_URL
""")
