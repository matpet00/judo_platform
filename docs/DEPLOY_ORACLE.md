# Nasazení Judo app na Oracle Cloud — krok za krokem

Cíl: aplikace běží **24/7 na internetu**, i když máš vypnutý počítač.  
Odhadovaný čas: **1–2 hodiny** (první registrace u Oracle může trvat déle).

---

## Přehled — co uděláš

1. Založíš účet Oracle Cloud (zdarma)
2. Vytvoříš malý server (VPS) ve Frankfurtu
3. Otevřeš porty pro web
4. Nahraješ kód z počítače
5. Spustíš instalační skript
6. Otevřeš `http://TVOJE_IP` v prohlížeči

Na serveru pak běží:

| Co | K čemu |
|----|--------|
| **Caddy** | Webová stránka + přesměrování `/api` na backend |
| **judo-api** | FastAPI (Python) |
| **`/var/lib/judo/`** | Databáze `judo.db` a přílohy |

---

## Část A — Příprava na Macu

### Krok A1: SSH klíč (pokud ještě nemáš)

V Terminálu na Macu:

```bash
ls ~/.ssh/id_ed25519.pub
```

- Pokud soubor **existuje**, přeskoč na A2.
- Pokud **neexistuje**, vytvoř klíč:

```bash
ssh-keygen -t ed25519 -C "tvuj@email.cz"
```

Stačí Enter u souboru i passphrase (nebo si passphrase nastav).

Zobraz veřejný klíč — **zkopíruješ ho v Oracle**:

```bash
cat ~/.ssh/id_ed25519.pub
```

Výstup začíná `ssh-ed25519 AAAA...` — celý řádek zkopíruj.

---

### Krok A2: Kód na server dostaneš jedním ze způsobů

**Způsob 1 — rsync z Macu (nejjednodušší, nepotřebuješ GitHub)**

Použiješ v části D. Jen měj projekt v `/Users/peter/Desktop/judo`.

**Způsob 2 — GitHub**

```bash
cd /Users/peter/Desktop/judo
git remote add origin https://github.com/TVUJ_USER/judo.git
git push -u origin main
```

Pak na serveru `git clone`. Repo musí být aspoň pro čtení dostupné (public nebo deploy token).

---

## Část B — Oracle Cloud účet a VM

### Krok B1: Registrace

1. Otevři [https://www.oracle.com/cloud/free/](https://www.oracle.com/cloud/free/)
2. **Start for free** → vyplň údaje (karta může být vyžadována kvůli ověření, Always Free by ti nemělo nic účtovat)
3. Po přihlášení vyber **region**: **Germany Central (Frankfurt)** — nejbližší EU k ČR

---

### Krok B2: Vytvoření instance (serveru)

1. Menu ☰ → **Compute** → **Instances**
2. **Create instance**

Vyplň:

| Pole | Hodnota |
|------|---------|
| **Name** | `judo` |
| **Image** | **Ubuntu 22.04** nebo **24.04** (Canonical) |
| **Shape** | Klikni **Change shape** → **Ampere** → **VM.Standard.A1.Flex** → 1 OCPU, 6 GB RAM (stačí; free tier dovolí víc) |
| **Networking** | Nech výchozí VCN; **Assign a public IPv4 address** = zapnuto |
| **SSH keys** | **Paste public key** → vlož obsah z `~/.ssh/id_ed25519.pub` |

3. **Create** — čekej 1–3 minuty, stav **Running**
4. Na stránce instance si zapiš **Public IP address** (např. `123.45.67.89`)

---

### Krok B3: Otevření portů (Security List) — často zapomenuté

Bez toho web z internetu nepůjde.

1. Na stránce instance klikni na odkaz **Subnet** (v sekci Instance details → Networking)
2. Klikni na **Security list** (např. Default Security List)
3. **Add ingress rules** — přidej **třikrát** (nebo jednu rule s port range, podle UI):

| Source CIDR | IP Protocol | Destination port |
|-------------|-------------|------------------|
| `0.0.0.0/0` | TCP | 22 |
| `0.0.0.0/0` | TCP | 80 |
| `0.0.0.0/0` | TCP | 443 |

4. **Add ingress rules** / ulož

---

### Krok B4: Přihlášení na server

Na Macu (nahraď IP):

```bash
ssh ubuntu@123.45.67.89
```

První připojení potvrď `yes`.  
Uživatel je **`ubuntu`** (ne root).

Máš-li chybu *Permission denied*, zkontroluj SSH klíč v Oracle a že instance běží.

---

## Část C — Instalace na serveru (přes SSH)

### Krok C1: Způsob rsync (bez GitHubu)

**Na Macu** (nový terminál, ne na serveru) — nahraď IP:

```bash
cd /Users/peter/Desktop/judo

rsync -avz --progress \
  --exclude .venv \
  --exclude frontend/node_modules \
  --exclude frontend/dist \
  --exclude .git \
  --exclude judo.db \
  --exclude 'judo.db-*' \
  --exclude uploads \
  --exclude .env \
  ./ ubuntu@123.45.67.89:~/judo/
```

**Na serveru** (SSH session):

```bash
cd ~/judo
sudo bash deploy/install.sh
```

Skript trvá cca 5–15 minut (stahuje Python, Node, Caddy, buildí frontend).

---

### Krok C1 alternativa: Git clone

**Na serveru:**

```bash
sudo apt-get update && sudo apt-get install -y git
sudo mkdir -p /opt/judo
sudo chown "$USER":"$USER" /opt/judo
git clone https://github.com/TVUJ_USER/judo.git /opt/judo
cd /opt/judo
sudo bash deploy/install.sh
```

---

### Krok C2: Co uvidíš po úspěšné instalaci

Na konci něco jako:

```
==============================================
 Hotovo.
 Otevři v prohlížeči: http://123.45.67.89
 Admin heslo (ulož si): xK9mP2...
 Konfigurace: /opt/judo/.env
==============================================
```

**Heslo si ulož** — je to přihlášení do administrace (`admin` + toto heslo).

Znovu ho zobrazíš:

```bash
grep ADMIN_PASSWORD /opt/judo/.env
```

---

## Část D — Ověření

### Krok D1: Health check

Na serveru:

```bash
curl -s http://127.0.0.1/api/health
```

Má vrátit: `{"status":"ok"}`

Z Macu (stejná IP):

```bash
curl -s http://123.45.67.89/api/health
```

Když lokálně OK ale z Macu ne → zkontroluj **Security List** (krok B3).

---

### Krok D2: Prohlížeč

1. Otevři **`http://123.45.67.89`** (svoji IP)
2. Mělo by se zobrazit menu klubu
3. **Trenér** — přihlášení PINem (po seedu výchozí `1234`)
4. **Admin** — uživatel `admin`, heslo z kroku C2

---

### Krok D3: Naplnění demo dat (volitelné)

Na **Macu** (s běžícím serverem), v projektu:

```bash
cd /Users/peter/Desktop/judo
source .venv/bin/activate

# Z API_WRITE_KEY na serveru:
ssh ubuntu@123.45.67.89 'grep API_WRITE_KEY /opt/judo/.env'

export BASE_URL=http://123.45.67.89/api
export API_WRITE_KEY=<hodnota ze serveru>
python scripts/reset_and_seed_demo.py
```

(Pozor: `BASE_URL` musí končit na `/api` nebo uprav skript — default v projektu je často `:8001` bez `/api`.)

Jednodušší varianta přímo na serveru po `pip install` v `/opt/judo`:

```bash
cd /opt/judo
source .env
export BASE_URL=http://127.0.0.1/api
export API_WRITE_KEY="$API_WRITE_KEY"
sudo -u judo .venv/bin/python scripts/reset_and_seed_demo.py
```

---

## Část E — Vlastní doména + HTTPS (až budeš chtít)

1. U registrátora domény **A záznam** → veřejná IP serveru
2. Na serveru uprav Caddy:

```bash
sudo nano /etc/caddy/Caddyfile
```

Nahraď řádek `:80 {` blokem (příklad):

```
judo.tvujklub.cz {
    root * /opt/judo/frontend/dist
    encode gzip

    handle /api/* {
        uri strip_prefix /api
        reverse_proxy 127.0.0.1:8001
    }

    handle {
        try_files {path} /index.html
        file_server
    }
}
```

3. Uprav CORS:

```bash
sudo nano /opt/judo/.env
# ALLOWED_ORIGINS=https://judo.tvujklub.cz
```

4. Restart:

```bash
sudo systemctl restart judo-api
sudo systemctl reload caddy
```

---

## Část F — Aktualizace po změnách v kódu

**rsync z Macu** (stejný příkaz jako C1), pak na serveru:

```bash
cd ~/judo && sudo bash deploy/update.sh
```

Nebo pokud používáš git v `/opt/judo`:

```bash
cd /opt/judo
git pull
sudo bash deploy/update.sh
```

---

## Řešení problémů

| Příznak | Co zkusit |
|---------|-----------|
| SSH nejde | Security List port 22; správný klíč v Oracle; instance Running |
| `curl` z Macu timeout | Security List 80/443; `sudo ufw status` na serveru |
| Stránka bílá / 502 | `sudo systemctl status judo-api caddy` |
| API 401 / zápisy nejdou | `sudo -u judo bash /opt/judo/deploy/build-app.sh` a `sudo systemctl restart judo-api` |
| CORS v konzoli prohlížeče | `ALLOWED_ORIGINS` v `.env` = přesně URL v adresním řádku |
| Zapomenuté admin heslo | `grep ADMIN_PASSWORD /opt/judo/.env` |

Logy API:

```bash
sudo journalctl -u judo-api -f
```

Logy Caddy:

```bash
sudo journalctl -u caddy -f
```

---

## Kontrolní seznam před ukázáním klubu

- [ ] Aplikace jde z mobilu přes mobilní data (ne jen z domácí WiFi)
- [ ] Admin heslo není výchozí slabé — změněno v `.env`
- [ ] Trenérské PINy změněny z `1234`
- [ ] Záloha: `sudo tar -czf judo-backup.tar.gz -C /var/lib judo`

---

## Rychlá reference — důležité cesty

| Co | Kde |
|----|-----|
| Aplikace | `/opt/judo` |
| Konfigurace | `/opt/judo/.env` |
| Databáze | `/var/lib/judo/judo.db` |
| Web soubory | `/opt/judo/frontend/dist` |
| Caddy config | `/etc/caddy/Caddyfile` |
