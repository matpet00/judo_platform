#!/usr/bin/env bash
# První nasazení na Ubuntu 22.04/24.04 (Oracle Cloud VPS).
# Spusť na serveru jako root z kořene repozitáře:
#   sudo bash deploy/install.sh
set -euo pipefail

if [[ "${EUID:-}" -ne 0 ]]; then
  echo "Spusť jako root: sudo bash deploy/install.sh" >&2
  exit 1
fi

APP_DIR=/opt/judo
DATA_DIR=/var/lib/judo
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

if [[ ! -f "$REPO_ROOT/app/main.py" ]]; then
  echo "Nespouštěj mimo kořen repozitáře (chybí app/main.py)." >&2
  exit 1
fi

echo "==> Balíčky (Python 3.11, Node 20, Caddy)…"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq curl git rsync ufw

if ! command -v python3.11 >/dev/null 2>&1; then
  apt-get install -y -qq software-properties-common
  add-apt-repository -y ppa:deadsnakes/ppa
  apt-get update -qq
  apt-get install -y -qq python3.11 python3.11-venv
fi

if ! command -v node >/dev/null 2>&1 || [[ "$(node -v 2>/dev/null || echo v0)" < "v20" ]]; then
  curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
  apt-get install -y -qq nodejs
fi

if ! command -v caddy >/dev/null 2>&1; then
  apt-get install -y -qq debian-keyring debian-archive-keyring apt-transport-https
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
    | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
    | tee /etc/apt/sources.list.d/caddy-stable.list >/dev/null
  apt-get update -qq
  apt-get install -y -qq caddy
fi

echo "==> Uživatel a adresáře…"
id -u judo >/dev/null 2>&1 || useradd --system --home "$APP_DIR" --shell /usr/sbin/nologin judo
mkdir -p "$APP_DIR" "$DATA_DIR/uploads"
chown -R judo:judo "$DATA_DIR"

echo "==> Kopie aplikace do $APP_DIR…"
rsync -a --delete \
  --exclude '.venv' \
  --exclude 'frontend/node_modules' \
  --exclude 'frontend/dist' \
  --exclude '.git' \
  --exclude 'judo.db' \
  --exclude 'judo.db-*' \
  --exclude 'uploads' \
  --exclude '.env' \
  "$REPO_ROOT/" "$APP_DIR/"
chown -R judo:judo "$APP_DIR"

echo "==> Produkční .env…"
ENV_FILE="$APP_DIR/.env"
PUBLIC_IP="$(curl -fsS -m 3 --connect-timeout 2 http://169.254.169.254/opc/v1/vnics/ 2>/dev/null \
  | python3.11 -c "import sys,json; d=json.load(sys.stdin); print(d[0]['publicIp'])" 2>/dev/null \
  || curl -fsS -m 5 ifconfig.me 2>/dev/null || true)"

if [[ ! -f "$ENV_FILE" ]]; then
  ORIGIN="${PUBLIC_IP:+http://${PUBLIC_IP}}"
  cat >"$ENV_FILE" <<EOF
DATABASE_URL=sqlite+aiosqlite:////var/lib/judo/judo.db
UPLOAD_DIR=/var/lib/judo/uploads
API_WRITE_KEY=$(openssl rand -hex 24)
JWT_SECRET=$(openssl rand -hex 32)
PIN_PEPPER=$(openssl rand -hex 16)
ADMIN_USERNAME=admin
ADMIN_PASSWORD=$(openssl rand -base64 18 | tr -d '/+=' | head -c 16)
ALLOWED_ORIGINS=${ORIGIN}
EOF
  if [[ -n "$PUBLIC_IP" ]]; then
    echo "    ALLOWED_ORIGINS=http://${PUBLIC_IP}"
  else
    echo "    Doplň ALLOWED_ORIGINS do $ENV_FILE (veřejná URL frontendu)."
  fi
fi

chown judo:judo "$ENV_FILE"
chmod 600 "$ENV_FILE"

echo "==> Build aplikace…"
sudo -u judo bash "$APP_DIR/deploy/build-app.sh"

echo "==> systemd + Caddy…"
install -m 644 "$APP_DIR/deploy/judo-api.service" /etc/systemd/system/judo-api.service
install -m 644 "$APP_DIR/deploy/Caddyfile" /etc/caddy/Caddyfile
systemctl daemon-reload
systemctl enable --now judo-api
systemctl enable --now caddy

echo "==> Firewall (ufw)…"
ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

ADMIN_PW="$(grep '^ADMIN_PASSWORD=' "$ENV_FILE" | cut -d= -f2- || true)"
echo ""
echo "=============================================="
echo " Hotovo."
if [[ -n "$PUBLIC_IP" ]]; then
  echo " Otevři v prohlížeči: http://${PUBLIC_IP}"
fi
echo " Admin heslo (ulož si): ${ADMIN_PW:-viz $ENV_FILE}"
echo " Konfigurace: $ENV_FILE"
echo ""
echo " Oracle: v Security List musí být otevřené porty 22, 80, 443."
echo " Aktualizace: cd $APP_DIR && git pull && sudo bash deploy/update.sh"
echo "=============================================="
