#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/eurusd-agent-bot}"
APPLY="${APPLY:-true}"
DEPLOY_RESTART="${DEPLOY_RESTART:-true}"
LOG_FILE="${LOG_FILE:-$APP_DIR/logs/autopilot.log}"
MIN_IMPROVEMENT="${MIN_IMPROVEMENT:-0.001}"

cd "$APP_DIR"
mkdir -p logs state/history data

{
  echo "==> $(date -u --iso-8601=seconds) EURUSD autopilot start"
  echo "==> Fetching fresh Yahoo data"
  docker compose run --rm eurusd-worker python -m eurusd_bot fetch-yahoo --out data/eurusd_5m.csv

  before_hash="$(sha256sum state/strategy.yaml | awk '{print $1}')"
  args=(python -m eurusd_bot.reflect --csv data/eurusd_5m.csv --min-improvement "$MIN_IMPROVEMENT")
  if [ "$APPLY" = "true" ]; then
    args+=(--apply)
  fi

  echo "==> Running reflection APPLY=$APPLY"
  docker compose run --rm eurusd-worker "${args[@]}" | tee state/last_reflection.json
  after_hash="$(sha256sum state/strategy.yaml | awk '{print $1}')"

  if [ "$before_hash" != "$after_hash" ]; then
    echo "==> Strategy changed"
    if [ "$DEPLOY_RESTART" = "true" ]; then
      echo "==> Restarting EURUSD worker to load volume strategy"
      docker compose up -d --build eurusd-worker
    fi
  else
    echo "==> No strategy change"
  fi

  echo "==> $(date -u --iso-8601=seconds) EURUSD autopilot done"
} 2>&1 | tee -a "$LOG_FILE"
