#!/usr/bin/env bash
set -euo pipefail

SERVICE_TYPE="${SERVICE_TYPE:-api}"
PORT="${PORT:-8000}"
ALEMBIC_TARGET="${ALEMBIC_TARGET:-head}"

case "$SERVICE_TYPE" in
  api)
    exec uvicorn api.main:app --host 0.0.0.0 --port "$PORT"
    ;;
  worker)
    exec python -m worker.worker
    ;;
  queue-manager|queue_manager)
    exec python -m core.queue_manager
    ;;
  alembic-upgrade)
    exec alembic upgrade "$ALEMBIC_TARGET"
    ;;
  alembic-downgrade)
    exec alembic downgrade "$ALEMBIC_TARGET"
    ;;
  *)
    # Allow overriding with an arbitrary command
    exec "$@"
    ;;
esac
