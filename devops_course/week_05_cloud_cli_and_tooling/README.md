# Week 5 — Cloud CLI and Tooling

The tools data engineers use every day that nobody explicitly teaches:
the AWS CLI for automating S3 and secrets work, Python environment
isolation so dependencies never fight, Makefiles to replace 12-step
READMEs with `make run`, and SSH to get into a failing server fast.

---

## Concept Files

| File | Topic |
|------|-------|
| `concepts/01_aws_cli_for_data_engineers.py` | AWS CLI setup, S3 operations, Secrets Manager, SSM Parameter Store, scripting with --query and jq |
| `concepts/02_environment_management_pyenv_virtualenv.py` | pyenv for Python versions, venv for package isolation, requirements files, poetry, direnv |
| `concepts/03_makefile_and_project_automation.py` | Makefile syntax, complete DE project Makefile, variables, chaining, the help target pattern |
| `concepts/04_ssh_remote_access_and_monitoring.py` | SSH keys, ~/.ssh/config aliases, tunneling to prod databases, live log monitoring, CloudWatch |

---

## Folder Structure

```
week_05_cloud_cli_and_tooling/
├── README.md
├── concepts/
│   ├── 01_aws_cli_for_data_engineers.py
│   ├── 02_environment_management_pyenv_virtualenv.py
│   ├── 03_makefile_and_project_automation.py
│   └── 04_ssh_remote_access_and_monitoring.py
├── practice/
│   └── exercises.py
└── projects/
    └── project_scaffold_generator.py
```

---

## How to Use This Week

Run each concept file to read through it with live output:

```bash
python3 concepts/01_aws_cli_for_data_engineers.py
python3 concepts/02_environment_management_pyenv_virtualenv.py
python3 concepts/03_makefile_and_project_automation.py
python3 concepts/04_ssh_remote_access_and_monitoring.py
```

Work through the exercises:

```bash
python3 practice/exercises.py
```

Try the project generator:

```bash
python3 projects/project_scaffold_generator.py --name my_pipeline
python3 projects/project_scaffold_generator.py --name my_pipeline --cloud aws --docker
```

---

## Practice Goals

After this week you should be able to:

1. **AWS CLI fluency** — list, upload, sync, and query S3 objects from the command line; generate presigned URLs; fetch secrets from Secrets Manager using both the CLI and boto3.

2. **Credential hygiene** — explain why hardcoded credentials are dangerous, set up IAM users with least privilege, know when to use .env vs Secrets Manager vs IAM roles.

3. **Environment isolation** — set up a new project from scratch: pyenv local, venv, requirements.in, pip-compile, .gitignore — without looking anything up.

4. **Makefile proficiency** — write a Makefile with standard targets (install, test, lint, run, clean, help), understand .PHONY and variables, run it in CI.

5. **SSH confidence** — create an SSH key pair, write ~/.ssh/config aliases for multiple servers, set up port-forwarding tunnels to access remote databases and UIs.

6. **Pipeline monitoring** — given an SSH session on a struggling server, run the right sequence of commands to diagnose high memory, find a stuck process, check live logs, and identify the root cause.

---

## Key Commands Cheat Sheet

### AWS CLI — S3

```bash
aws s3 ls                                         # list all buckets
aws s3 ls s3://bucket/prefix/ --recursive         # list all objects
aws s3 cp file.csv s3://bucket/prefix/            # upload
aws s3 sync ./data/ s3://bucket/data/             # sync local → S3
aws s3 sync s3://bucket/data/ ./local/            # sync S3 → local
aws s3 sync ./data/ s3://bucket/ --exclude "*.tmp"
aws s3 presign s3://bucket/file.csv --expires-in 3600
aws s3 ls s3://bucket/ --recursive --human-readable --summarize  # total size
aws s3api list-objects --bucket b | jq '.Contents[] | select(.Size > 1000000)'
```

### AWS CLI — Secrets

```bash
aws sts get-caller-identity                        # who am I?
aws secretsmanager get-secret-value --secret-id NAME --query SecretString --output text
aws ssm get-parameter --name /app/key --with-decryption
```

### Python Environments

```bash
pyenv install 3.11.6                              # install Python version
pyenv local 3.11.6                                # pin version for this directory
python -m venv .venv                              # create virtual environment
source .venv/bin/activate                         # activate (Mac/Linux)
pip install pip-tools && pip-compile requirements.in  # generate locked deps
pip install -r requirements.txt                   # install from lock file
```

### Makefile

```bash
make help           # show all documented targets
make install-dev    # set up venv + install deps
make test           # run tests
make lint           # check code style
make format         # auto-format
make run            # run pipeline
make run ENV=prod   # run with variable override
make clean          # remove build artifacts
```

### SSH

```bash
ssh-keygen -t ed25519 -C "email"                  # generate key pair
ssh pipeline-prod                                  # connect via ~/.ssh/config alias
ssh -L 5432:rds-host:5432 user@bastion-host        # tunnel Postgres
ssh -L 8080:localhost:8080 user@airflow-server     # tunnel Airflow UI
ssh -N -f -L 5432:rds:5432 user@bastion           # background tunnel
scp fix.py user@host:/app/src/                     # copy file to server
rsync -avz ./src/ user@host:/app/src/              # sync directory
ssh pipeline-prod 'tail -f /var/log/etl.log'       # tail remote log locally
```

### Monitoring (on remote server)

```bash
free -h                           # RAM usage
df -h                             # disk usage
ps aux --sort=-%mem | head -10    # top memory processes
tail -f /var/log/pipeline.log     # live log following
journalctl -u pipeline.service -f # systemd service logs
watch -n 5 'df -h && free -h'    # refresh every 5 seconds
kill <pid>                        # graceful stop (SIGTERM)
```

---

## Security Rules (Non-Negotiable)

- **Never hardcode credentials** — not in .py files, not in config files
- **Never commit .env to git** — add it to .gitignore from commit #1
- **Never use root AWS credentials** — create IAM users with least privilege
- **Use IAM roles on EC2/ECS/Lambda** — no long-lived keys on servers
- **Use Secrets Manager for production passwords** — not .env files on servers
- **chmod 600 on private key files** — SSH refuses to use them otherwise
- **Rotate any leaked credentials immediately** — git history is permanent
