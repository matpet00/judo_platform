# Judo club API

Minimální FastAPI + async SQLite (SQLAlchemy 2 + `aiosqlite`) pro žáky, trenéry a rodiče.

## Nastavení

```bash
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Volitelně zkopírujte `.env.example` na `.env` a doplňte SMTP pro odesílání e-mailů.

## Spuštění

```bash
uvicorn app.main:app --reload --port 8001
```

- Dokumentace API: http://127.0.0.1:8001/docs  
- SQLite soubor (výchozí): `./judo.db` (vznikne při startu v aktuálním adresáři)

### Demo žáci (Orlova) přes API

Po spuštění API můžeš z kořene projektu vytvořit **30 fiktivních žáků** na pobočce **Orlova** čistě voláním REST (žádný seed v aplikaci):

```bash
python scripts/populate_orlova_students.py
```

Jiný port (např. výchozí uvicorn 8000): `BASE_URL=http://127.0.0.1:8000 python scripts/populate_orlova_students.py`

Skript má výchozí `BASE_URL` **:8001** (stejně jako příkaz výše). Očekává, že na tom URL už běží **toto** API (`GET /health` → `{"status":"ok"}`). Když `GET /branches` vrátí **404**, na daném portu typicky běží jiná aplikace — spusť `uvicorn` z adresáře **judo** v druhém terminálu, nebo nastav správný `BASE_URL`.

Trenér **Petr Matej** na Orlově (jednorázově přes API, pokud ještě neexistuje):

```bash
python scripts/create_trainer_petr_matej_orlova.py
```

## Endpointy (shrnutí)

| Metoda | Cesta | Popis |
|--------|--------|--------|
| GET | `/health` | Stav API |
| GET | `/branches` | Seznam poboček + **`students`** a **`trainers`** (zjednodušené objekty) |
| GET | `/branches/{id}` | Jedna pobočka včetně **`students`** a **`trainers`** |
| POST | `/branches` | Nová pobočka (odpověď stejný tvar; `students` / `trainers` obvykle `[]`) |
| PATCH | `/branches/{id}` | Částečná úprava `name` / `address`; odpověď včetně **`students`** a **`trainers`** |
| DELETE | `/branches/{id}` | Smazání pobočky (409, pokud má žáky nebo trenéry) |
| GET | `/trainers` | Seznam trenérů |
| POST | `/trainers` | Trenér: `first_name`, `last_name`, **`branch_ids`** (1+ poboček, M:N) |
| PATCH | `/trainers/{id}` | Částečná úprava; volitelně **`branch_ids`** (nahradí celý seznam, min. 1) |
| DELETE | `/trainers/{id}` | Smazání trenéra |
| GET | `/parents` | Seznam rodičů |
| POST | `/parents` | Rodič: `first_name`, `last_name`, `email`, `phone` |
| PATCH | `/parents/{id}` | Částečná úprava: `first_name`, `last_name`, `email`, `phone` |
| DELETE | `/parents/{id}` | Smazání rodiče (odpadnou vazby na žáky) |
| GET | `/students` | Seznam žáků |
| POST | `/students` | Žák: `first_name`, `last_name`, `age_group`, **`branch_ids`** (1+ poboček, M:N), `parents` … |
| PATCH | `/students/{id}` | Částečná úprava; volitelně **`branch_ids`** (nahradí celý seznam, min. 1) nebo **`parents`** … |
| DELETE | `/students/{id}` | Smazání žáka |
| GET | `/training-sessions` | Seznam tréninků (volitelně `?branch_id=`, `?trainer_id=`) |
| POST | `/training-sessions` | Nový trénink (`branch_id`, `starts_at`, volitelně `trainer_id`, `age_group`, `notes`) |
| GET | `/training-sessions/{id}` | Trénink včetně **`attendance_records`** |
| PATCH | `/training-sessions/{id}` | Částečná úprava tréninku |
| DELETE | `/training-sessions/{id}` | Smazání tréninku (včetně docházky) |
| GET | `/training-sessions/{id}/attendance` | Docházka na tréninku |
| POST | `/training-sessions/{id}/attendance` | Záznam docházky (`student_id`, `status`, volitelně `recorded_by_id`) |
| GET/PATCH/DELETE | `/training-sessions/{id}/attendance/{attendance_id}` | Jedna záznam docházky |
| GET | `/students/{id}/attendance` | Historie docházky žáka (volitelně `?session_id=`) |
| POST | `/mail/parents` | E-mail rodičům (`parent_ids`, `subject`, `body`) — vyžaduje SMTP v `.env` |

**PATCH:** posílej jen pole, která chceš změnit; prázdné tělo → **400** `No fields to update.`

Bez `SMTP_HOST` a `SMTP_FROM` vrátí `/mail/parents` **503**.

**Žák i trenér ↔ pobočka:** vztah **M:N** — pole **`branch_ids`** při zápisu, v odpovědi **`branches`** (řazeno podle id pobočky).

**Docházka:** `status` je `present`, `absent` nebo `excused`. Žák musí být na pobočce tréninku; pokud má trénink `age_group`, musí sedět se žákem. Jedna docházka na pár (trénink, žák) — duplicitní **POST** → **409**.

**Výchozí seed poboček** (viz `DEFAULT_BRANCHES` v [`app/models.py`](app/models.py)): Orlova, Dolni Lutyne, Petrvald + fiktivní adresy.

**Migrace schématu:** při změně sloupců v SQLite smažte lokální `judo.db` a nechte aplikaci znovu vytvořit tabulky při startu. U entit pobočka, trenér, rodič a žák odpovědi obsahují `created_at` a `updated_at` (časová razítka z databáze).

## Skupiny věku

`U8`, `U10`, `U12`, `U14`, `U16`, `U18` — pole `age_group` u `POST /students`.
