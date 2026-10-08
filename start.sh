#!/usr/bin/env bash
set -euo pipefail
python check_production.py
python bootstrap.py
exec gunicorn app:app --bind "0.0.0.0:${PORT:-10000}" --workers 1 --threads 4 --timeout 90 --access-logfile - --error-logfile -
