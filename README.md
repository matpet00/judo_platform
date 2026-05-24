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
| POST | `/trainers` | Trenér: `first_name`, `last_name`, **`branch`** (`Orlova` \| `Dolni Lutyne` \| `Petrvald`) |
| GET | `/trainers` | Seznam trenérů včetně `id` a pobočky (ladění) |
| GET | `/branches` | Seznam poboček: `name`, **`address`** (seed při startu) |
| POST | `/parents` | Rodič: `first_name`, `last_name`, `email`, **`phone`** |
| GET | `/parents` | Seznam rodičů (ladění) |
| POST | `/students` | Žák: `branch` (`Orlova` \| `Dolni Lutyne` \| `Petrvald`), `age_group`, `parents` … |
| GET | `/students` | Seznam žáků včetně `branch` a rodičů |
| POST | `/mail/parents` | E-mail rodičům podle **`parent_ids`** (interní ID z odpovědi API; `subject`, `body`) — vyžaduje SMTP v `.env` |

Bez `SMTP_HOST` a `SMTP_FROM` vrátí `/mail/parents` **503**.

**Migrace schématu:** při změně sloupců v SQLite smažte lokální `judo.db` a nechte aplikaci znovu vytvořit tabulky při startu.

## Pobočky

`Orlova`, `Dolni Lutyne`, `Petrvald` — v `POST /students` / `POST /trainers` pole **`branch`** (přesný řetězec / enum ve Swaggeru). Každá pobočka má v DB i **`address`** (zatím fiktivní hodnoty ze seedu v `app/models.py`).

## Skupiny věku

`U8`, `U10`, `U12`, `U14`, `U16`, `U18` — pole `age_group` u `POST /students`.
