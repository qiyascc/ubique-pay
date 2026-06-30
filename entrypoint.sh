#!/bin/sh
# Migrate + collect static, then run the given command (gunicorn by default).
set -e

python manage.py migrate --noinput
python manage.py collectstatic --noinput

exec "$@"
