#!/usr/bin/env bash
# Sestaví backend deps + frontend production build. Spouštěj z /opt/judo.
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$APP_DIR"

if [[ ! -f .env ]]; then
  echo "Chybí $APP_DIR/.env — nejdřív spusť deploy/install.sh" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1091
source .env
set +a

if [[ ! -d .venv ]]; then
  python3.11 -m venv .venv
fi
.venv/bin/pip install -q -U pip
.venv/bin/pip install -q -r requirements.txt

cd frontend
if [[ -f package-lock.json ]]; then
  npm ci
else
  npm install
fi
VITE_API_URL=/api npm run build

echo "Build hotový: frontend/dist"
