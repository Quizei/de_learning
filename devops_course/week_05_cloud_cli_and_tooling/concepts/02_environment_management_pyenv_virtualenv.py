"""
Environment Management — pyenv, virtualenv, poetry, direnv
===========================================================
The most frustrating hour in data engineering isn't a complex bug —
it's "but it works on my machine" followed by two hours debugging
Python version and package conflicts.

This file covers:
- The problem: why Python environment isolation matters
- pyenv: manage multiple Python versions side by side
- venv: isolate packages per project
- requirements files: reproducible installs
- poetry: modern dependency management for new projects
- direnv: auto-activate environments on cd

Run this file: python3 concepts/02_environment_management_pyenv_virtualenv.py
Some commands are actually run (python3 --version, which python3).
pyenv/poetry/direnv commands are printed since they may not be installed.
"""

import subprocess
import sys
import os


# ============================================================
# HELPERS
# ============================================================

def section(title):
    print()
    print("=" * 70)
    print(f"  {title}")
    print("=" * 70)


def show(cmd, note=""):
    """Run a command and print its output."""
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
    """Print a command with its purpose — does NOT execute it."""
    print(f"\n  $ {cmd}")
    if note:
        print(f"  # {note}")


# ============================================================
# 1. THE PROBLEM
# ============================================================

section("1. THE PROBLEM — Why Isolation Matters")

print("""
  Imagine you work on two data pipelines simultaneously:

    Project A (legacy pipeline):
      - Python 3.8 (company standard at the time)
      - pandas 1.5.3 (uses deprecated API removed in pandas 2.0)
      - psycopg2 2.9.1

    Project B (new lakehouse pipeline):
      - Python 3.11 (for performance improvements)
      - pandas 2.0.1 (new ArrowDtype support for Parquet)
      - psycopg2 2.9.6

  Without isolation:
    You install Project B's packages → they overwrite Project A's.
    Now Project A crashes because pandas 2.0 removed the API it uses.
    You downgrade pandas → Project B crashes.
    You've lost a morning to pip install whack-a-mole.

  Same problem at the Python version level:
    macOS ships with Python 3.9 (or older).
    Your pipeline needs 3.11. You can't upgrade system Python
    without potentially breaking system tools.

  The solution stack:
    ┌─────────────────────────────────────────────────────────┐
    │  pyenv                                                   │
    │  Install and switch between Python versions             │
    │  python 3.8.18, 3.10.12, 3.11.6 all coexist           │
    │  ─────────────────────────────────────────────────────  │
    │  venv (virtual environment)                             │
    │  Isolated package set per project directory             │
    │  project_a/.venv: pandas 1.5.3, psycopg2 2.9.1        │
    │  project_b/.venv: pandas 2.0.1, psycopg2 2.9.6        │
    └─────────────────────────────────────────────────────────┘

  pyenv controls which Python binary is used.
  venv controls which packages that Python binary can see.
  Together they give you complete isolation.
""")


# ============================================================
# 2. PYENV — MANAGE PYTHON VERSIONS
# ============================================================

section("2. PYENV — Multiple Python Versions on One Machine")

print("""
  INSTALLATION:
  ─────────────────────────────────────────────────────────────────────
""")

demo(
    "brew install pyenv",
    note="macOS — installs pyenv via Homebrew"
)

print("""
  After installing, add to your shell profile (~/.zshrc or ~/.bashrc):
    export PYENV_ROOT="$HOME/.pyenv"
    export PATH="$PYENV_ROOT/bin:$PATH"
    eval "$(pyenv init -)"

  Then restart your shell: exec $SHELL
""")

print("""
  CORE COMMANDS:
  ─────────────────────────────────────────────────────────────────────
""")

demo(
    "pyenv install --list | grep '3.1'",
    note="See all available Python 3.1x versions you can install"
)

demo(
    "pyenv install 3.11.6",
    note="Download and compile Python 3.11.6 (takes 2-5 minutes)"
)

demo(
    "pyenv install 3.10.12",
    note="Install another version — they coexist peacefully"
)

demo(
    "pyenv versions",
    note="List all installed Python versions"
)

print("""
  Sample output:
      system
    * 3.11.6 (set by /Users/you/.pyenv/version)
      3.10.12
      3.8.18
""")

demo(
    "pyenv global 3.11.6",
    note="Set the default Python version for your entire machine"
)

demo(
    "pyenv local 3.10.12",
    note="Set Python version for THIS DIRECTORY only (creates .python-version file)"
)

print("""
  The .python-version file:
    - Created in the current directory by 'pyenv local'
    - Contains just the version number: "3.10.12"
    - COMMIT this to git: it tells your teammates which Python to use
    - pyenv automatically uses it when you cd into the directory

  Example repo root:
    my_pipeline/
    ├── .python-version    ← "3.10.12" — pyenv reads this automatically
    ├── requirements.txt
    └── src/
""")

demo(
    "pyenv shell 3.9.18",
    note="Temporarily use a different Python just for this shell session"
)

print("""
  Priority order (pyenv checks top to bottom):
    1. pyenv shell   — current shell session (overrides everything)
    2. pyenv local   — .python-version file in current or parent directory
    3. pyenv global  — your machine-wide default
    4. system        — the OS's built-in Python (fallback)
""")

print("\n  Current Python (actually running):")
show("python3 --version", note="Which Python version is active right now?")
show("which python3", note="Where is the active python3 binary?")


# ============================================================
# 3. VIRTUAL ENVIRONMENTS (venv)
# ============================================================

section("3. VIRTUAL ENVIRONMENTS — Isolate Packages Per Project")

print("""
  venv is built into Python 3.3+ — no installation needed.
  It creates a self-contained directory with:
    - Its own python binary (symlinked to the base Python)
    - Its own pip
    - Its own site-packages (where pip install puts things)

  When the venv is ACTIVE, Python only sees packages in that venv.
  Other projects' packages are completely invisible.
""")

demo(
    "python -m venv .venv",
    note="Create a virtual environment in the .venv directory"
)

print("""
  Why .venv (with the dot)?
    The dot makes it a "hidden" directory on Unix — ls won't show it.
    But more importantly: .venv is the convention that most tools
    recognize (VS Code, PyCharm, black, ruff all look for .venv).
""")

demo(
    "source .venv/bin/activate",
    note="Activate the venv (macOS/Linux)"
)

demo(
    r".venv\Scripts\activate",
    note="Activate the venv (Windows)"
)

print("""
  After activation, your prompt changes:
    Before: user@machine project %
    After:  (.venv) user@machine project %

  The (.venv) prefix is your signal that the venv is active.
  Now 'python' and 'pip' point to the venv, not the system.
""")

demo(
    "pip install pandas sqlalchemy psycopg2-binary boto3",
    note="Install packages — goes into .venv/lib/pythonX.Y/site-packages/"
)

demo(
    "deactivate",
    note="Leave the venv — (.venv) disappears from prompt"
)

print("""
  .venv/ in your .gitignore — NON-NEGOTIABLE:
    .venv contains hundreds of megabytes of compiled packages.
    It's machine-specific (macOS vs Linux binary differences).
    It's reproducible from requirements.txt.
    NEVER commit .venv to git.

  Minimal .gitignore for a Python project:
    .venv/
    __pycache__/
    *.pyc
    .env
    *.egg-info/
    dist/
    .DS_Store
""")


# ============================================================
# 4. REQUIREMENTS FILES
# ============================================================

section("4. REQUIREMENTS FILES — Reproducible Installs")

print("""
  requirements.txt is the oldest approach — still widely used.

  CREATING IT:
""")

demo(
    "pip freeze > requirements.txt",
    note="Snapshot ALL installed packages and their exact versions"
)

print("""
  Output looks like:
    boto3==1.34.0
    botocore==1.34.0
    certifi==2023.11.17
    charset-normalizer==3.3.2
    ...50+ more lines...

  The problem with pip freeze:
    It includes EVERYTHING — transitive dependencies too.
    You asked for 'pandas'. You get pandas + numpy + python-dateutil + pytz.
    Now your requirements.txt has 50 entries for 5 packages you care about.
    Worse: it makes updates hard (change pandas version → ripple effects).
""")

print("""
  THE TWO-TIER APPROACH (recommended):
  ─────────────────────────────────────────────────────────────────────
  requirements.in  — what you ACTUALLY need (just your direct deps)
  requirements.txt — generated file with ALL transitive deps pinned

  requirements.in example:
    pandas>=2.0
    sqlalchemy>=2.0
    boto3
    psycopg2-binary
    pytest

  Then use pip-tools to compile:
""")

demo(
    "pip install pip-tools",
    note="Install pip-tools (do this in your dev venv)"
)

demo(
    "pip-compile requirements.in",
    note="Resolve all transitive deps and write pinned requirements.txt"
)

print("""
  pip-compile generates:
    # This file is autogenerated by pip-compile with Python 3.11
    # Do not edit this file — edit requirements.in instead
    boto3==1.34.0
    botocore==1.34.0         # via boto3
    numpy==1.26.3            # via pandas
    pandas==2.1.4
    ...

  Workflow:
    1. Edit requirements.in (add/remove packages)
    2. Run pip-compile (regenerates requirements.txt)
    3. pip install -r requirements.txt
    4. Commit BOTH files

  Separate dev dependencies:
    requirements.in          — runtime deps (pandas, sqlalchemy)
    requirements-dev.in      — dev-only deps (pytest, black, ruff)
""")


# ============================================================
# 5. POETRY — MODERN DEPENDENCY MANAGEMENT
# ============================================================

section("5. POETRY — Modern Alternative for New Projects")

print("""
  Poetry solves dependency management, packaging, and publishing
  in one tool. For data pipelines (not libraries), you mainly use it
  for dependency management and reproducible installs.

  Advantages over pip + requirements.txt:
    - Single pyproject.toml (replaces setup.py, requirements.txt, etc.)
    - poetry.lock pins ALL transitive deps reproducibly
    - Dependency resolution at install time (no conflicts)
    - Built-in venv management (creates and manages the venv for you)
    - Separates dev and runtime deps cleanly

  INSTALLATION:
""")

demo(
    "curl -sSL https://install.python-poetry.org | python3 -",
    note="Official installer — poetry lives outside any project venv"
)

print("""
  STARTING A NEW PROJECT:
""")

demo(
    "poetry new my_pipeline",
    note="Scaffold a new project with src layout, tests, pyproject.toml"
)

print("""
  Generated structure:
    my_pipeline/
    ├── pyproject.toml      ← project metadata + dependencies
    ├── README.md
    ├── my_pipeline/
    │   └── __init__.py
    └── tests/
        └── __init__.py
""")

demo(
    "poetry add pandas",
    note="Add a dependency — updates pyproject.toml and poetry.lock"
)

demo(
    "poetry add pytest --group dev",
    note="Add a dev-only dependency (won't be installed in production)"
)

demo(
    "poetry install",
    note="Install ALL deps from poetry.lock (reproducible, exact versions)"
)

demo(
    "poetry run python src/pipeline.py",
    note="Run a command in the poetry venv without activating it"
)

demo(
    "poetry shell",
    note="Open a subshell with the poetry venv activated"
)

demo(
    "poetry update pandas",
    note="Upgrade pandas to latest allowed version, update poetry.lock"
)

print("""
  poetry.lock — ALWAYS commit this file:
    It contains the exact version of every package (including transitive).
    When a teammate runs 'poetry install', they get the IDENTICAL environment.
    No "it works on my machine" — everyone has the exact same packages.

  pyproject.toml example:
    [tool.poetry]
    name = "my-pipeline"
    version = "0.1.0"
    python = "^3.11"

    [tool.poetry.dependencies]
    pandas = "^2.0"
    sqlalchemy = "^2.0"
    boto3 = "*"

    [tool.poetry.group.dev.dependencies]
    pytest = "^7.0"
    black = "^23.0"
    ruff = "*"

  pip vs poetry — when to use what:
    Existing project with requirements.txt → keep using pip
    New project, team agreement → poetry (better DX, cleaner deps)
    Library you'll publish to PyPI → poetry (best-in-class for this)
    Data science notebook work → conda or pip+venv (poetry overkill)
""")


# ============================================================
# 6. DIRENV — AUTO-ACTIVATE ENVS
# ============================================================

section("6. DIRENV — Auto-Activate Your Venv on cd")

print("""
  The problem direnv solves:
    You cd into a project and forget to activate the venv.
    You run 'python pipeline.py' and import errors fly because
    you're using the system Python without your packages.

  direnv is a shell extension that automatically runs .envrc files
  when you enter a directory — and reverses them when you leave.

  INSTALLATION:
""")

demo(
    "brew install direnv",
    note="Install direnv (macOS)"
)

print("""
  Add to your shell profile (~/.zshrc):
    eval "$(direnv hook zsh)"
  Or for bash (~/.bashrc):
    eval "$(direnv hook bash)"

  SETUP PER PROJECT:
""")

demo(
    "echo 'source .venv/bin/activate' > .envrc",
    note="Create .envrc that activates your venv"
)

demo(
    "direnv allow",
    note="Authorize direnv to run .envrc in this directory (security prompt)"
)

print("""
  Now:
    cd ~/projects/my_pipeline    → (.venv) activates automatically
    cd ~/projects/other_project  → (.venv) deactivates automatically

  More powerful .envrc — load .env AND activate venv:
    # .envrc
    source .venv/bin/activate
    dotenv .env                  # direnv built-in: load .env file

  Or manually:
    # .envrc
    source .venv/bin/activate
    export $(grep -v "^#" .env | xargs)

  .envrc goes in .gitignore or you can commit a safe version:
    # Commitable version (no secrets, just venv activation):
    source .venv/bin/activate

  The .env file with real secrets ALWAYS goes in .gitignore.
  The .envrc that loads it is fine to commit (it has no secrets).
""")


# ============================================================
# QUICK REFERENCE
# ============================================================

print()
print("=" * 70)
print("  QUICK REFERENCE — Environment Management")
print("=" * 70)
print("""
  PYENV:
    pyenv install --list | grep '3.1'   list available versions
    pyenv install 3.11.6                install a Python version
    pyenv versions                      list installed versions
    pyenv global 3.11.6                 set machine-wide default
    pyenv local 3.10.12                 set for this directory (.python-version)
    pyenv shell 3.9.18                  set for this shell session only

  VENV:
    python -m venv .venv                create virtual environment
    source .venv/bin/activate           activate (macOS/Linux)
    .venv\\Scripts\\activate             activate (Windows)
    deactivate                          leave virtual environment
    which python                        confirm you're in the venv

  PIP / REQUIREMENTS:
    pip install -r requirements.txt     install from pinned file
    pip freeze > requirements.txt       snapshot current packages
    pip install pip-tools               install pip-compile
    pip-compile requirements.in         generate pinned requirements.txt

  POETRY:
    poetry new my_pipeline              scaffold new project
    poetry add pandas                   add dependency
    poetry add pytest --group dev       add dev dependency
    poetry install                      install from lock file
    poetry run python script.py         run without activating shell
    poetry shell                        activate poetry venv

  DIRENV:
    brew install direnv                 install
    echo 'source .venv/bin/activate' > .envrc
    direnv allow                        authorize .envrc

  .GITIGNORE (always include these):
    .venv/
    __pycache__/
    *.pyc
    .env
    .python-version   (optional: some teams commit this)
""")
