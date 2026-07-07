#!/usr/bin/env bash
# Aktualizace po git pull na serveru: sudo bash deploy/update.sh
set -euo pipefail

if [[ "${EUID:-}" -ne 0 ]]; then
  echo "Spusť jako root: sudo bash deploy/update.sh" >&2
  exit 1
fi

APP_DIR=/opt/judo
cd "$APP_DIR"

sudo -u judo bash "$APP_DIR/deploy/build-app.sh"
systemctl restart judo-api
systemctl reload caddy || systemctl restart caddy

echo "Aktualizace dokončena."
