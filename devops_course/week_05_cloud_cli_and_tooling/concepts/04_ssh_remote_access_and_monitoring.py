"""
SSH, Remote Access, and Pipeline Monitoring
============================================
Your pipeline is running on a server somewhere. Something is wrong.
SSH is how you get there. Knowing what to run when you arrive is
how you fix it before the daily report is late.

This file covers:
- SSH fundamentals: connecting securely to remote servers
- SSH key pairs: why passwords are inferior
- ~/.ssh/config: the underused file that saves minutes every day
- scp and rsync: copying files to/from remote servers
- SSH tunneling: access remote databases from your local SQL client
- Monitoring live pipelines: logs, processes, disk, memory
- CloudWatch Logs: AWS-native log management
- Alerting basics: detecting pipeline failures programmatically

Run this file: python3 concepts/04_ssh_remote_access_and_monitoring.py
SSH commands are printed — no remote server needed.
Commands that work locally (ssh -V, which ssh) are actually run.
"""

import subprocess


# ============================================================
# HELPERS
# ============================================================

def section(title):
    print()
    print("=" * 70)
    print(f"  {title}")
    print("=" * 70)


def show(cmd, note=""):
    """Run a command locally and print output."""
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
    """Print a command without executing it."""
    print(f"\n  $ {cmd}")
    if note:
        print(f"  # {note}")


# ============================================================
# 1. SSH FUNDAMENTALS
# ============================================================

section("1. SSH FUNDAMENTALS")

print("""
  SSH (Secure Shell) is an encrypted protocol for accessing remote machines.
  When your pipeline runs on an EC2 server, an RDS proxy, or any Linux machine,
  SSH is how you connect to it interactively.

  Think of it as: remote control for servers.

  Everything you type is encrypted. Even on a public network, no one can
  see your commands, your file contents, or your passwords in transit.
""")

demo(
    "ssh ubuntu@192.168.1.100",
    note="Connect as user 'ubuntu' to server at that IP address"
)

demo(
    "ssh -i ~/.ssh/mykey.pem ec2-user@54.123.45.67",
    note="Connect to AWS EC2 using a PEM key file (standard AWS pattern)"
)

print("""
  Common EC2 usernames by AMI:
    Amazon Linux:    ec2-user
    Ubuntu:          ubuntu
    Debian:          admin
    CentOS:          centos
    RHEL:            ec2-user

  What happens when you connect:
    1. Your SSH client and server perform a cryptographic handshake
    2. Server authenticates YOU (via password or key pair)
    3. You get a shell on the remote machine
    4. Everything you type is encrypted end-to-end

  Exiting:
    exit       — type this to close the SSH session
    Ctrl+D     — EOF signal, also closes the session
    ~.         — force-close if the connection has hung
""")


# ============================================================
# 2. SSH KEY PAIRS
# ============================================================

section("2. SSH KEY PAIRS — Why Keys Beat Passwords")

print("""
  Password authentication weaknesses:
    - Brute-forceable (bots attempt thousands of passwords per second)
    - You might use the same password as other services
    - If someone sees you type it, they have it
    - AWS EC2 instances disable password auth by default (keys only)

  Key pair authentication:
    - Mathematical relationship between two files
    - Private key: stays on YOUR machine, never shared, never transmitted
    - Public key: placed on the server (in ~/.ssh/authorized_keys)
    - Authentication: "Can you prove you hold the private key to this public key?"
      Without ever sending the private key.

  Analogy:
    Public key  = a padlock (you can hand it to anyone)
    Private key = the key to that padlock (you keep this always)
    The server puts your padlock on the door. You open it with your key.
""")

demo(
    'ssh-keygen -t ed25519 -C "muneeb@company.com"',
    note="Generate an Ed25519 key pair (modern, fast, secure)"
)

print("""
  Why Ed25519 over RSA:
    - Shorter keys, same or better security
    - Faster generation and connection handshake
    - RSA-4096 is still fine but Ed25519 is the current best practice

  What ssh-keygen creates:
    ~/.ssh/id_ed25519      ← PRIVATE KEY — never share this, never copy to servers
    ~/.ssh/id_ed25519.pub  ← PUBLIC KEY — this is what you put on servers

  Secure your private key — it's your master access credential.
    - NEVER email it
    - NEVER commit it to git
    - NEVER paste it in Slack
    - The .pem files AWS gives you are private keys
""")

demo(
    "ssh-copy-id ubuntu@192.168.1.100",
    note="Append your public key to the server's ~/.ssh/authorized_keys"
)

print("""
  Or manually:
    cat ~/.ssh/id_ed25519.pub
    # Copy the output, then on the server:
    # echo "<paste_public_key>" >> ~/.ssh/authorized_keys

  AWS EC2 workflow:
    - Create a key pair in AWS Console (or import your public key)
    - AWS puts your public key into the EC2 instance at launch
    - You keep the .pem file (your private key) → use: ssh -i file.pem
""")


# ============================================================
# 3. ~/.ssh/config — THE UNDERUSED FILE
# ============================================================

section("3. ~/.ssh/config — The File That Saves Minutes Every Day")

print("""
  Without ~/.ssh/config, you type this every time:
    ssh -i ~/.ssh/prod.pem -p 22 ec2-user@54.123.45.67

  With ~/.ssh/config, you type:
    ssh pipeline-prod

  ~/.ssh/config contains named aliases for servers you access regularly.
  It's one of those tools where 10 minutes of setup saves hours over time.
""")

print("""
  Example ~/.ssh/config:
  ─────────────────────────────────────────────────────────────────────
""")

print("""
  # ~/.ssh/config

  # Development Airflow server
  Host airflow-dev
      HostName 10.0.1.50
      User ubuntu
      IdentityFile ~/.ssh/dev.pem
      ServerAliveInterval 60
      ServerAliveCountMax 3

  # Staging data processing server
  Host pipeline-staging
      HostName staging.internal.company.com
      User ec2-user
      IdentityFile ~/.ssh/staging.pem
      Port 22

  # Production EC2 — use with caution
  Host pipeline-prod
      HostName 54.123.45.67
      User ec2-user
      IdentityFile ~/.ssh/prod.pem
      ServerAliveInterval 60
      ServerAliveCountMax 3

  # Bastion host (jump box) — access internal servers through it
  Host bastion
      HostName bastion.company.com
      User ec2-user
      IdentityFile ~/.ssh/bastion.pem

  # Access internal server THROUGH the bastion
  Host prod-internal
      HostName 10.0.2.100
      User ubuntu
      IdentityFile ~/.ssh/prod.pem
      ProxyJump bastion
""")

print("""
  Now you can:
""")

demo("ssh airflow-dev", note="Instead of: ssh -i ~/.ssh/dev.pem ubuntu@10.0.1.50")
demo("ssh pipeline-prod", note="Instead of: ssh -i ~/.ssh/prod.pem ec2-user@54.123.45.67")
demo("ssh prod-internal", note="SSH through bastion automatically — no manual proxy setup")

print("""
  Key config options:
    HostName         the actual IP or DNS name
    User             remote username
    IdentityFile     which private key to use
    Port             SSH port (default: 22)
    ServerAliveInterval  send keepalive every N seconds (prevents timeout)
    ServerAliveCountMax  how many keepalives before giving up
    ProxyJump        connect through another SSH host (bastion pattern)

  PERMISSIONS — required for SSH to work:
""")

demo(
    "chmod 700 ~/.ssh",
    note="SSH directory: owner read/write/execute only"
)

demo(
    "chmod 600 ~/.ssh/id_ed25519",
    note="Private key: owner read/write only (SSH refuses if too permissive)"
)

demo(
    "chmod 644 ~/.ssh/id_ed25519.pub",
    note="Public key: owner read/write, others read-only"
)

demo(
    "chmod 600 ~/.ssh/config",
    note="Config file: owner read/write only"
)

print("""
  SSH will REFUSE to use a private key if permissions are too open.
  Error: "WARNING: UNPROTECTED PRIVATE KEY FILE!" means you need chmod 600.
""")


# ============================================================
# 4. SCP AND RSYNC
# ============================================================

section("4. scp AND rsync — Copying Files To/From Servers")

print("""
  scp (secure copy) — simple file transfer over SSH:
""")

demo(
    "scp pipeline.py ubuntu@10.0.1.50:/app/src/",
    note="Copy local file to remote server"
)

demo(
    "scp -i ~/.ssh/dev.pem pipeline.py ubuntu@10.0.1.50:/app/src/",
    note="Copy with explicit key file"
)

demo(
    "scp ubuntu@10.0.1.50:/var/log/pipeline.log ./logs/",
    note="Copy file FROM remote server to local ./logs/ directory"
)

demo(
    "scp -r ./src/ ubuntu@10.0.1.50:/app/",
    note="Copy entire directory recursively (-r flag)"
)

print("""
  rsync — smarter file sync (recommended over scp for directories):
""")

demo(
    "rsync -avz ./src/ ubuntu@10.0.1.50:/app/src/",
    note="Sync local src/ to remote — only transfers changed files"
)

print("""
  rsync flags:
    -a   archive mode: preserves permissions, timestamps, symlinks
    -v   verbose: show what's being transferred
    -z   compress data during transfer (faster over slow networks)
    --delete    remove remote files that don't exist locally (mirror)
    --dry-run   preview what WOULD transfer without transferring

  rsync vs scp:
    scp:   copies everything every time (like 'cp')
    rsync: compares and copies only differences (like 'sync')

  For large datasets (many files), rsync is dramatically faster on
  subsequent runs because it skips files that haven't changed.
""")

demo(
    "rsync -avz --dry-run ./data/ ubuntu@10.0.1.50:/data/raw/",
    note="Preview what rsync would transfer without actually doing it"
)

demo(
    "rsync -avz --delete ./src/ ubuntu@10.0.1.50:/app/src/",
    note="Mirror: copy changes AND delete remote files not in local src/"
)


# ============================================================
# 5. SSH TUNNELING
# ============================================================

section("5. SSH TUNNELING — Data Engineering's Secret Weapon")

print("""
  SSH tunneling (port forwarding) lets you connect to services on a remote
  server AS IF they were running on your local machine.

  Why this is essential for data engineers:
    - Production Postgres is on a private subnet (no direct internet access)
    - You want to query it from your local DBeaver or pgAdmin
    - SSH tunnel: creates an encrypted bridge from your laptop to prod

  Syntax:
    ssh -L local_port:remote_host:remote_port user@ssh_server

  Reading it: "Forward connections to localhost:LOCAL_PORT through
               SSH_SERVER and deliver them to REMOTE_HOST:REMOTE_PORT"
""")

demo(
    "ssh -L 5432:localhost:5432 ubuntu@pipeline-prod",
    note="Tunnel production Postgres (port 5432) to your local port 5432"
)

print("""
  After running this:
    - You have an SSH session open
    - In another terminal: psql -h localhost -p 5432 -U etl_user -d prod_db
    - That connection travels through the encrypted SSH tunnel to prod

  Real-world data engineering tunnels:
""")

demo(
    "ssh -L 5432:prod-db.cluster.us-east-1.rds.amazonaws.com:5432 ubuntu@bastion",
    note="Tunnel to RDS through a bastion server (RDS has no public IP)"
)

demo(
    "ssh -L 8080:localhost:8080 ubuntu@airflow-server",
    note="Tunnel Airflow webserver UI to http://localhost:8080"
)

demo(
    "ssh -L 5601:localhost:5601 ubuntu@elasticsearch-server",
    note="Tunnel Kibana dashboard to http://localhost:5601"
)

demo(
    "ssh -L 9200:localhost:9200 ubuntu@elasticsearch-server",
    note="Tunnel Elasticsearch REST API to localhost:9200"
)

demo(
    "ssh -N -L 5432:prod-db.rds.amazonaws.com:5432 ubuntu@bastion",
    note="-N means: tunnel only, don't open a shell (good for background tunnels)"
)

demo(
    "ssh -N -f -L 5432:prod-db.rds.amazonaws.com:5432 ubuntu@bastion",
    note="-f sends tunnel to background — runs silently, you keep your terminal"
)

print("""
  Background tunnel management:
    # Start background tunnel
    ssh -N -f -L 5432:prod-db.rds.amazonaws.com:5432 ubuntu@bastion

    # Find and kill the tunnel later
    ps aux | grep ssh | grep '5432'
    kill <pid>

  Pro tip: Add tunnel aliases to ~/.bashrc:
    alias tunnel-prod-db='ssh -N -f -L 5432:prod-db.rds.amazonaws.com:5432 ubuntu@bastion'
    alias tunnel-airflow='ssh -N -f -L 8080:localhost:8080 ubuntu@airflow-server'

  Then:
    tunnel-prod-db && psql -h localhost -p 5432 -U etl_user prod_db
""")


# ============================================================
# 6. MONITORING RUNNING PIPELINES
# ============================================================

section("6. MONITORING PIPELINES ON REMOTE SERVERS")

print("""
  You've SSH'd into the server where your pipeline is running.
  What do you run first? Here's the diagnostic sequence.
""")

demo(
    "tail -f /var/log/pipeline.log",
    note="Follow live log output — press Ctrl+C to stop watching"
)

demo(
    "tail -n 200 /var/log/pipeline.log | grep ERROR",
    note="Last 200 lines, filtered to only show ERRORs"
)

demo(
    "journalctl -u pipeline.service -f",
    note="Follow logs of a systemd service (for managed processes)"
)

demo(
    "journalctl -u pipeline.service --since '1 hour ago'",
    note="Show logs from the last hour for a systemd service"
)

demo(
    "ps aux | grep python",
    note="Find all running Python processes — see your pipeline PID"
)

demo(
    "top",
    note="Real-time process monitor — CPU%, memory%, all processes (press q to quit)"
)

demo(
    "htop",
    note="Better top — color UI, easier to navigate (brew install htop)"
)

demo(
    "df -h",
    note="Disk usage of all mounted filesystems in human-readable format"
)

demo(
    "du -sh /var/log/*",
    note="Size of each item in /var/log — find what's eating disk"
)

demo(
    "free -h",
    note="RAM usage: total, used, free, cached"
)

demo(
    "watch -n 5 'df -h && echo && free -h'",
    note="Refresh disk + memory stats every 5 seconds — watch for filling disk"
)

demo(
    "lsof -p <pid> | wc -l",
    note="Count open file handles for a process — high = file handle leak"
)

print("""
  Combining SSH + monitoring (run from your local machine):
""")

demo(
    "ssh pipeline-prod 'tail -f /var/log/etl.log'",
    note="Tail a remote log without staying in an interactive shell"
)

demo(
    "ssh pipeline-prod 'ps aux | grep python && df -h'",
    note="Quick remote diagnostic — processes and disk"
)

demo(
    "ssh pipeline-prod 'journalctl -u pipeline.service --since 1h --no-pager | grep ERROR'",
    note="Get errors from the last hour in one shot from your local terminal"
)


# ============================================================
# 7. CLOUDWATCH LOGS (AWS)
# ============================================================

section("7. CLOUDWATCH LOGS — AWS-Native Log Management")

print("""
  When your pipeline runs on EC2, ECS, Lambda, or any AWS service,
  CloudWatch Logs is where structured log storage happens.

  Your code sends logs to CloudWatch. You query them with:
    - The AWS CLI (for quick ad-hoc queries)
    - CloudWatch Log Insights (for SQL-like queries)
    - boto3 (for programmatic access)
""")

demo(
    "aws logs tail /myapp/pipeline --follow",
    note="Live tail — equivalent to tail -f for CloudWatch log groups"
)

demo(
    "aws logs tail /myapp/pipeline --since 1h",
    note="Show log events from the last hour"
)

demo(
    "aws logs filter-log-events --log-group-name /myapp/pipeline --filter-pattern 'ERROR'",
    note="Filter to only ERROR messages across all log streams"
)

demo(
    "aws logs filter-log-events --log-group-name /myapp/pipeline --start-time $(date -d '1 hour ago' +%s000) --filter-pattern '{$.level = \"ERROR\"}'",
    note="Filter ERRORs from the last hour (structured JSON logs)"
)

print("""
  boto3 equivalent — fetch logs in Python:

  import boto3
  from datetime import datetime, timedelta

  def get_recent_errors(log_group: str, hours: int = 1) -> list:
      client = boto3.client("logs", region_name="us-east-1")
      start_ms = int((datetime.utcnow() - timedelta(hours=hours)).timestamp() * 1000)
      response = client.filter_log_events(
          logGroupName=log_group,
          startTime=start_ms,
          filterPattern="ERROR",
      )
      return [event["message"] for event in response["events"]]

  errors = get_recent_errors("/myapp/pipeline")
  if errors:
      print(f"Found {len(errors)} errors in the last hour!")
      for e in errors[:5]:
          print(f"  {e}")
""")


# ============================================================
# 8. ALERTING BASICS
# ============================================================

section("8. ALERTING BASICS — Know When Your Pipeline Breaks")

print("""
  The worst pipeline failure is the one nobody notices for three days.
  Alerting means you know within minutes.

  WHAT TO ALERT ON:
  ─────────────────────────────────────────────────────────────────────
  1. ERROR count spike     — more errors than usual in recent logs
  2. Pipeline didn't start — expected pipeline at 3am but no logs since 2:30am
  3. Processing too slow   — took 4 hours instead of usual 30 minutes
  4. Disk > 85% full       — pipeline will fail when disk fills up
  5. Memory > 90% used     — OOM kill is coming

  SIMPLE ALERTING APPROACH — bash + Slack webhook:
  ─────────────────────────────────────────────────────────────────────
  Many teams start with a simple shell script run by cron:
""")

print("""
  #!/bin/bash
  # check_pipeline.sh — run every 15 minutes via cron

  LOG_FILE="/var/log/pipeline.log"
  SLACK_WEBHOOK="https://hooks.slack.com/services/T00000/B00000/xxxxxxxx"
  ERROR_THRESHOLD=5

  # Count errors in the last 15 minutes
  RECENT_ERRORS=$(journalctl -u pipeline.service --since "15 minutes ago" | grep -c "ERROR")

  if [ "$RECENT_ERRORS" -gt "$ERROR_THRESHOLD" ]; then
      MESSAGE="ALERT: $RECENT_ERRORS errors in pipeline.service in last 15 minutes"
      curl -s -X POST "$SLACK_WEBHOOK" \\
          -H 'Content-type: application/json' \\
          -d "{\\"text\\": \\":red_circle: $MESSAGE\\"}"
  fi

  # Check if disk is >85% full
  DISK_USAGE=$(df / | awk 'NR==2 {gsub("%",""); print $5}')
  if [ "$DISK_USAGE" -gt 85 ]; then
      curl -s -X POST "$SLACK_WEBHOOK" \\
          -H 'Content-type: application/json' \\
          -d "{\\"text\\": \\":warning: Disk usage at $DISK_USAGE% on pipeline server\\"}"
  fi
""")

demo(
    "crontab -e",
    note="Edit your crontab — add this to run check_pipeline.sh every 15 minutes"
)

print("""
  Cron entry to run every 15 minutes:
    */15 * * * * /home/ubuntu/check_pipeline.sh >> /var/log/monitor.log 2>&1

  For AWS pipelines, use CloudWatch Alarms instead:
    - Set alarm on: log metric filter for "ERROR" count > threshold
    - Notify via SNS → sends email and/or Slack
    - No server needed — fully managed
""")


# ============================================================
# 9. LOCAL CHECKS (actually run these)
# ============================================================

section("9. LOCAL SSH CHECKS (running now)")

show("which ssh", note="Is SSH client installed?")
show("ssh -V", note="SSH version")

import os
ssh_dir = os.path.expanduser("~/.ssh")
config_file = os.path.join(ssh_dir, "config")

print(f"\n  Checking ~/.ssh directory:")
if os.path.isdir(ssh_dir):
    print(f"    ~/.ssh exists")
    files = os.listdir(ssh_dir)
    print(f"    Files: {', '.join(files) if files else '(empty)'}")
    if "config" in files:
        print(f"    ~/.ssh/config exists — you have server aliases configured")
    else:
        print(f"    No ~/.ssh/config yet — create one to save server connection settings")
else:
    print(f"    ~/.ssh does not exist yet")
    print(f"    Run 'ssh-keygen -t ed25519' to create it")


# ============================================================
# QUICK REFERENCE
# ============================================================

print()
print("=" * 70)
print("  QUICK REFERENCE — SSH and Remote Monitoring")
print("=" * 70)
print("""
  CONNECT:
    ssh user@host                         basic connection
    ssh -i ~/.ssh/key.pem user@host       with key file
    ssh myserver                          using ~/.ssh/config alias

  KEY MANAGEMENT:
    ssh-keygen -t ed25519 -C "email"      generate key pair
    ssh-copy-id user@host                 install public key on server
    chmod 600 ~/.ssh/id_ed25519           fix private key permissions

  FILE TRANSFER:
    scp local.py user@host:/path/         copy file to server
    scp user@host:/path/file.log ./       copy from server
    rsync -avz ./src/ user@host:/app/     sync directory (smart)
    rsync -avz --dry-run ...              preview without transferring

  TUNNELING:
    ssh -L 5432:localhost:5432 user@host          tunnel Postgres
    ssh -L 8080:localhost:8080 user@host          tunnel web UI
    ssh -N -f -L 5432:rds-host:5432 user@bastion  background tunnel

  MONITORING (on remote server):
    tail -f /var/log/pipeline.log         live log following
    journalctl -u service.name -f         systemd service logs
    ps aux | grep python                  find pipeline process
    df -h                                 disk usage
    free -h                               RAM usage
    watch -n 5 'df -h && free -h'        refresh every 5 seconds
    top                                   live process monitor

  FROM LOCAL (no SSH session needed):
    ssh host 'tail -f /var/log/etl.log'   remote log from local terminal
    ssh host 'ps aux | grep python'       remote process check

  AWS CLOUDWATCH:
    aws logs tail /myapp/pipeline --follow
    aws logs filter-log-events --log-group-name /myapp/pipeline --filter-pattern 'ERROR'
""")
