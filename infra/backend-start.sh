#!/bin/sh
set -eu
python manage.py migrate --noinput
if [ "${SEED_DEMO:-false}" = "true" ]; then
  python manage.py seed_demo --credentials-file /data/demo-credentials.json
fi
exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 2 --timeout 30 --access-logfile /dev/null
