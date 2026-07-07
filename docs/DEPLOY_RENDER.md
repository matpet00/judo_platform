# Nasazení na Render.com — krok za krokem

Cíl: aplikace běží **24/7 v cloudu** (i s vypnutým PC).  
Registrace: **e-mail + GitHub**, bez formuláře bydliště jako u Oracle.

**Omezení free tieru:**
- API po ~15 min nečinnosti **usne** → první načtení trvá 30–60 s
- SQLite se při **redeploy** může vymazat (pro testování stačí; data znovu seedneš)
- Render občas chce **platební kartu** na ověření (peníze se nestrhávají, pokud zůstaneš na Free)

---

## Co se vytvoří

| Služba | URL (příklad) | Účel |
|--------|---------------|------|
| **judo-api** | `https://judo-api-xxxx.onrender.com` | FastAPI backend |
| **judo-web** | `https://judo-web-xxxx.onrender.com` | React frontend |

V repu je připravený soubor **`render.yaml`** — Render z něj obě služby vytvoří sám.

---

## Část 1 — GitHub (10 min)

Render nejjednodušší funguje s Git repozitářem.

### 1. Vytvoř repo na GitHubu

1. [github.com/new](https://github.com/new) → název např. `judo`
2. **Private** nebo Public — podle tebe

### 2. Nahraj kód z Macu

```bash
cd /Users/peter/Desktop/judo

git remote add origin https://github.com/TVUJ_USER/judo.git
git push -u origin main
```

(Pokud `origin` už existuje, použij `git push`.)

---

## Část 2 — Render účet (5 min)

1. [render.com](https://render.com) → **Get Started**
2. Přihlášení přes **GitHub** (doporučeno)
3. Povol Renderu přístup k repozitáři `judo`
4. Karta — jen pokud Render vyzve (ověření identity)

---

## Část 3 — Blueprint deploy (10–20 min)

### 4. Vytvoř služby z `render.yaml`

1. Render Dashboard → **New +** → **Blueprint**
2. Vyber repozitář **judo**
3. Render načte `render.yaml` — uvidíš **judo-api** a **judo-web**
4. **Apply**

Render začne buildit obě služby (první deploy trvá cca 10–20 min).

### 5. Po dokončení deploye

V dashboardu u služby **judo-web** klikni na URL → mělo by se otevřít menu klubu.

Health check API:

```bash
curl -s https://judo-api-xxxx.onrender.com/health
```

→ `{"status":"ok"}`

---

## Část 4 — Přihlašovací údaje

### Admin heslo

Render Dashboard → **judo-api** → **Environment** → proměnná **`ADMIN_PASSWORD`**  
(Uživatel: `admin`.)

### API klíč (pro skripty)

V **judo-api** → **Environment** → **`API_WRITE_KEY`**

---

## Část 5 — Demo data (volitelné)

Na Macu (nahraď URL a klíč z Render dashboardu):

```bash
cd /Users/peter/Desktop/judo
source .venv/bin/activate

export BASE_URL=https://judo-api-xxxx.onrender.com
export API_WRITE_KEY=<z Render Environment>
export ADMIN_PASSWORD=<z Render Environment>

pip install httpx  # pokud chybí
python scripts/reset_and_seed_demo.py
```

> Skript posílá `X-API-Key`, pokud je nastavená proměnná `API_WRITE_KEY`.

---

## Aktualizace po změnách v kódu

```bash
git add .
git commit -m "Popis změny"
git push
```

Render **automaticky** znovu nasadí obě služby (Auto-Deploy je výchozí).

---

## Časté problémy

| Problém | Řešení |
|---------|--------|
| Build frontendu spadne | Logy u **judo-web** → často chybí `VITE_API_URL`; zkontroluj, že **judo-api** už běží |
| CORS v prohlížeči | **judo-api** → `ALLOWED_ORIGINS` musí být URL **judo-web** (mělo se nastavit z blueprintu) |
| 401 na zápisy | `VITE_API_WRITE_KEY` při buildu = `API_WRITE_KEY` na API → redeploy **judo-web** |
| Prázdná DB po deployi | Free tier — SQLite je efemérní; znovu seed nebo Admin |
| Pomalé první načtení | Free tier — API se probouzí ze spánku, chvíli počkej |

---

## Když blueprint nefunguje — ruční vytvoření

### Služba A: judo-api

- **New +** → **Web Service**
- Repo `judo`, branch `main`
- **Runtime:** Python 3
- **Build:** `pip install -r requirements.txt`
- **Start:** `bash deploy/render-start.sh`
- **Plan:** Free, **Region:** Frankfurt
- **Environment:**
  - `DATABASE_URL` = `sqlite+aiosqlite:///./judo.db`
  - `JWT_SECRET`, `API_WRITE_KEY`, `PIN_PEPPER` → Generate
  - `ADMIN_PASSWORD` → Generate
  - `ALLOWED_ORIGINS` = `https://TVOJE-WEB-URL.onrender.com` (doplníš po vytvoření webu)

### Služba B: judo-web

- **New +** → **Static Site**
- **Build:** `cd frontend && npm install && npm run build`
- **Publish:** `frontend/dist`
- **Environment (build time):**
  - `VITE_API_URL` = `https://TVOJE-API-URL.onrender.com`
  - `VITE_API_WRITE_KEY` = stejné jako `API_WRITE_KEY` z API
- **Redirects/Rewrites:** `/*` → `/index.html` (SPA)

---

## Bezpečnost před ukázáním klubu

- [ ] Změnit `ADMIN_PASSWORD` v Render Environment
- [ ] Změnit trenérské PINy z `1234`
- [ ] Repo private, pokud nechceš veřejný kód

---

## Porovnání s Oracle

| | Render Free | Oracle VPS |
|--|-------------|------------|
| Registrace | GitHub + e-mail | Adresa, karta, hodně údajů |
| SQLite trvalé | Spíš ne (redeploy) | Ano |
| Spánek | API usíná | Ne |
| Náš deploy skript | `render.yaml` | `deploy/install.sh` |
