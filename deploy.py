#!/usr/bin/env python3
"""Ubique Pay — production deploy (Gunicorn + systemd + Nginx).

Generates and installs a systemd socket+service running Gunicorn, an Nginx
site that proxies to it, and (optionally) a Let's Encrypt certificate. Run as
root on an Ubuntu/Debian host after `install.py`:

    sudo python3 deploy.py

Configuration is read from .env / environment:
    DEPLOY_DOMAIN, DEPLOY_APP_NAME, GUNICORN_WORKERS, GUNICORN_BIND
"""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV = ROOT / ".venv"


def load_env():
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def run(cmd):
    print(f"  $ {' '.join(cmd)}")
    subprocess.check_call(cmd)


def write_root(path, content):
    print(f"  → {path}")
    Path(path).write_text(content)


def require_root():
    if os.geteuid() != 0:
        sys.exit("deploy.py must be run as root (use: sudo python3 deploy.py).")


def main():
    require_root()
    load_env()

    app = os.environ.get("DEPLOY_APP_NAME", "ubique-pay")
    domain = os.environ.get("DEPLOY_DOMAIN", "")
    user = os.environ.get("DEPLOY_USER", os.environ.get("SUDO_USER", "www-data"))
    gunicorn = VENV / "bin" / "gunicorn"

    if not domain:
        sys.exit("Set DEPLOY_DOMAIN in .env first.")
    if not gunicorn.exists():
        sys.exit("Run install.py first (gunicorn not found in .venv).")

    print(f"\n▶ Deploying {app} for {domain}")

    # 1) systemd socket
    write_root(f"/etc/systemd/system/{app}.socket", f"""[Unit]
Description={app} gunicorn socket

[Socket]
ListenStream=/run/{app}.sock

[Install]
WantedBy=sockets.target
""")

    # 2) systemd service
    write_root(f"/etc/systemd/system/{app}.service", f"""[Unit]
Description={app} gunicorn daemon
Requires={app}.socket
After=network.target

[Service]
User={user}
Group=www-data
WorkingDirectory={ROOT}
EnvironmentFile={ROOT}/.env
ExecStart={gunicorn} -c {ROOT}/gunicorn.conf.py config.wsgi:application
Restart=on-failure

[Install]
WantedBy=multi-user.target
""")

    # 3) nginx site
    write_root(f"/etc/nginx/sites-available/{app}", f"""server {{
    listen 80;
    server_name {domain};

    location = /favicon.ico {{ access_log off; log_not_found off; }}
    location /static/ {{ alias {ROOT}/staticfiles/; }}

    location / {{
        include proxy_params;
        proxy_pass http://unix:/run/{app}.sock;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }}
}}
""")
    link = f"/etc/nginx/sites-enabled/{app}"
    if not os.path.islink(link):
        os.symlink(f"/etc/nginx/sites-available/{app}", link)

    # 4) enable + start
    run(["systemctl", "daemon-reload"])
    run(["systemctl", "enable", "--now", f"{app}.socket"])
    run(["systemctl", "restart", f"{app}.service"])
    run(["nginx", "-t"])
    run(["systemctl", "restart", "nginx"])

    print(f"\n\033[1;32m✔ Deployed.\033[0m  http://{domain}")
    print(f"  TLS:  sudo certbot --nginx -d {domain}")
    print(f"  Logs: journalctl -u {app}.service -f")


if __name__ == "__main__":
    main()
