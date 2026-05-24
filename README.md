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
uvicorn app.main:app --reload
```

- Dokumentace API: http://127.0.0.1:8000/docs  
- SQLite soubor (výchozí): `./judo.db` (vznikne při startu v aktuálním adresáři)

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
| POST | `/mail/parents` | E-mail rodičům (`parent_ids`, `subject`, `body`) — vyžaduje SMTP v `.env` |

**PATCH:** posílej jen pole, která chceš změnit; prázdné tělo → **400** `No fields to update.`

Bez `SMTP_HOST` a `SMTP_FROM` vrátí `/mail/parents` **503**.

**Žák i trenér ↔ pobočka:** vztah **M:N** — pole **`branch_ids`** při zápisu, v odpovědi **`branches`** (řazeno podle id pobočky).

**Výchozí seed poboček** (viz `DEFAULT_BRANCHES` v [`app/models.py`](app/models.py)): Orlova, Dolni Lutyne, Petrvald + fiktivní adresy.

**Migrace schématu:** při změně sloupců v SQLite smažte lokální `judo.db` a nechte aplikaci znovu vytvořit tabulky při startu. U entit pobočka, trenér, rodič a žák odpovědi obsahují `created_at` a `updated_at` (časová razítka z databáze).

## Skupiny věku

`U8`, `U10`, `U12`, `U14`, `U16`, `U18` — pole `age_group` u `POST /students`.
