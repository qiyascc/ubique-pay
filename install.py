#!/usr/bin/env python3
"""Ubique Pay — local/installer bootstrap.

Creates a virtualenv, installs dependencies, prepares the .env file, runs
database migrations and collects static files. Idempotent and safe to re-run.

    python3 install.py
"""

import os
import secrets
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV = ROOT / ".venv"
PY = VENV / "bin" / "python"
PIP = VENV / "bin" / "pip"


def run(cmd, **kw):
    print(f"  $ {' '.join(str(c) for c in cmd)}")
    subprocess.check_call(cmd, **kw)


def step(msg):
    print(f"\n\033[1;36m▶ {msg}\033[0m")


def ensure_venv():
    step("Creating virtual environment (.venv)")
    if not VENV.exists():
        run([sys.executable, "-m", "venv", str(VENV)])
    else:
        print("  already exists")


def install_deps():
    step("Installing dependencies")
    run([str(PIP), "install", "-q", "--upgrade", "pip"])
    run([str(PIP), "install", "-q", "-r", str(ROOT / "requirements.txt")])


def ensure_env():
    step("Preparing .env")
    env = ROOT / ".env"
    if env.exists():
        print("  .env already exists")
        return
    example = (ROOT / ".env.example").read_text()
    key = secrets.token_urlsafe(64)
    example = example.replace("DJANGO_SECRET_KEY=\n", f"DJANGO_SECRET_KEY={key}\n")
    env.write_text(example)
    print("  .env created with a fresh DJANGO_SECRET_KEY")


def django(*args):
    run([str(PY), str(ROOT / "manage.py"), *args])


def migrate_and_static():
    step("Running migrations")
    django("migrate", "--noinput")
    step("Collecting static files")
    django("collectstatic", "--noinput")


def main():
    os.chdir(ROOT)
    ensure_venv()
    install_deps()
    ensure_env()
    migrate_and_static()
    print("\n\033[1;32m✔ Install complete.\033[0m")
    print("  Dev server:  .venv/bin/python manage.py runserver")
    print("  Superuser:   .venv/bin/python manage.py createsuperuser")
    print("  Production:  sudo python3 deploy.py")


if __name__ == "__main__":
    main()
