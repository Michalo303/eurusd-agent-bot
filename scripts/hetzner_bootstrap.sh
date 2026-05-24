#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/eurusd-agent-bot}"
REPO_URL="${REPO_URL:-https://github.com/Michalo303/eurusd-agent-bot.git}"
BRANCH="${BRANCH:-main}"

echo "==> Installing base packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y ca-certificates curl git ufw

if ! command -v docker >/dev/null 2>&1; then
  echo "==> Installing Docker"
  curl -fsSL https://get.docker.com | sh
fi

echo "==> Enabling Docker"
systemctl enable --now docker

echo "==> Configuring firewall"
ufw allow OpenSSH
ufw --force enable

echo "==> Preparing app directory"
mkdir -p "$(dirname "$APP_DIR")"
if [ -d "$APP_DIR/.git" ]; then
  git -C "$APP_DIR" fetch origin "$BRANCH"
  git -C "$APP_DIR" reset --hard "origin/$BRANCH"
else
  rm -rf "$APP_DIR"
  git clone --branch "$BRANCH" "$REPO_URL" "$APP_DIR"
fi

cd "$APP_DIR"
mkdir -p data logs state/history

echo "==> Starting worker"
docker compose up -d --build

echo "==> Status"
docker compose ps
docker compose logs --tail=80 eurusd-worker

