#!/usr/bin/env bash
set -o errexit

python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python manage.py collectstatic --noinput
python manage.py migrate

if [ "$SEED_DEMO_DATA" = "true" ] || [ "$SEED_DEMO_DATA" = "True" ]; then
  python manage.py seed_tilisi
fi
