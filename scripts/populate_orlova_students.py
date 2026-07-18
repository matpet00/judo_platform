#!/usr/bin/env python3
"""Vytvoří 30 demo žáků na pobočce Orlova voláním běžného REST API.

V jiném terminálu z kořene projektu (složka judo) spusť API:

    uvicorn app.main:app --reload

Pak:

    python scripts/populate_orlova_students.py

Jiný host/port: BASE_URL=http://127.0.0.1:8010 python scripts/populate_orlova_students.py
"""

from __future__ import annotations

import os
import sys

import httpx

BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8001").rstrip("/")

_JUDO_HINT = f"""
Zkontroluj:
  1) V druhém terminálu z kořene projektu (složka judo) běží: uvicorn app.main:app --reload
  2) V prohlížeči otevřeš {BASE_URL}/docs a vidíš titulek aplikace „Judo club“
  3) GET {BASE_URL}/health vrací {{"status":"ok"}}
  4) Na stejném hostu/portu nemáš jinou aplikaci — jinak nastav BASE_URL (viz docstring skriptu).
""".strip()
BRANCH_NAME = "Orlova"
TOTAL = 30

# Česká křestní jména dětí (30)
FIRST_NAMES = (
    "Tereza",
    "Jan",
    "Eliška",
    "Matěj",
    "Anna",
    "Jakub",
    "Kateřina",
    "Lukáš",
    "Barbora",
    "Martin",
    "Eva",
    "Ondřej",
    "Veronika",
    "Petr",
    "Lucie",
    "Michal",
    "Markéta",
    "David",
    "Jana",
    "Filip",
    "Hana",
    "Pavel",
    "Zuzana",
    "Daniel",
    "Alena",
    "Radek",
    "Lenka",
    "Václav",
    "Andrea",
    "Jiří",
)

# Česká příjmení (30)
LAST_NAMES = (
    "Novák",
    "Svoboda",
    "Novotný",
    "Dvořák",
    "Černý",
    "Procházka",
    "Kučera",
    "Veselý",
    "Horák",
    "Mareš",
    "Pospíšil",
    "Hájek",
    "Jelínek",
    "Urban",
    "Blažek",
    "Krejčí",
    "Holub",
    "Soukup",
    "Polák",
    "Staněk",
    "Beneš",
    "Šimek",
    "Moravec",
    "Navrátil",
    "Tůma",
    "Kadlec",
    "Bartoš",
    "Pečka",
    "Čermák",
    "Sedláček",
)

AGE_GROUPS = ("U8", "U10", "U12", "U14", "U16", "U18", "U21", "Over21")

# Jména rodičů (střídání matka/otec)
PARENT_FIRST = (
    "Marie",
    "Petr",
    "Jana",
    "Tomáš",
    "Eva",
    "Martin",
    "Lenka",
    "Pavel",
    "Hana",
    "Ondřej",
    "Kateřina",
    "Michal",
    "Veronika",
    "David",
    "Lucie",
    "Filip",
    "Markéta",
    "Jakub",
    "Barbora",
    "Lukáš",
    "Anna",
    "Radek",
    "Zuzana",
    "Daniel",
    "Alena",
    "Jiří",
    "Tereza",
    "Jan",
    "Eliška",
    "Matěj",
)

PARENT_LAST = (
    "Svobodová",
    "Novák",
    "Dvořáková",
    "Černý",
    "Horáková",
    "Veselý",
    "Kučerová",
    "Procházka",
    "Benešová",
    "Mareš",
    "Jelínková",
    "Urban",
    "Pospíšilová",
    "Hájek",
    "Novotná",
    "Holub",
    "Krejčíová",
    "Staněk",
    "Moravcová",
    "Navrátil",
    "Šimková",
    "Tůma",
    "Kadlecová",
    "Bartoš",
    "Pečková",
    "Sedláček",
    "Čermáková",
    "Bláhová",
    "Polák",
    "Soukupová",
)


def _fail(msg: str, response: httpx.Response | None = None) -> None:
    print(msg, file=sys.stderr)
    if response is not None:
        print(response.text, file=sys.stderr)
    sys.exit(1)


def _expect_judo_health(client: httpx.Client) -> None:
    try:
        h = client.get("/health")
    except httpx.ConnectError as e:
        _fail(
            f"Nepodařilo se připojit k {BASE_URL!r}: {e}\n\n"
            f"Nejspíš API vůbec neběží na tomto hostu/portu.\n{_JUDO_HINT}",
        )
    if h.status_code != 200:
        _fail(
            f"GET /health vrátilo {h.status_code} (očekávám 200 a Judo API).\n{_JUDO_HINT}",
            h,
        )
    try:
        body = h.json()
    except ValueError:
        _fail(f"GET /health nevrátilo JSON.\n{_JUDO_HINT}", h)
    if not isinstance(body, dict) or body.get("status") != "ok":
        _fail(
            f"Na {BASE_URL!r} neběží Judo club API (GET /health musí vracet {{\"status\":\"ok\"}}).\n{_JUDO_HINT}",
            h,
        )


def main() -> None:
    with httpx.Client(base_url=BASE_URL, timeout=60.0) as client:
        _expect_judo_health(client)

        try:
            r = client.get("/branches")
        except httpx.ConnectError as e:
            _fail(f"Nepodařilo se připojit k {BASE_URL!r}: {e}")

        if r.status_code != 200:
            _fail(
                f"GET /branches selhalo ({r.status_code}).\n"
                f"Když /health funguje, ale /branches ne, BASE_URL míří na špatnou aplikaci nebo za reverse proxy s prefixem cesty.\n"
                f"{_JUDO_HINT}",
                r,
            )

        branches = r.json()
        orlova = next((b for b in branches if b.get("name") == BRANCH_NAME), None)
        if orlova is None:
            _fail(f'Pobočka "{BRANCH_NAME}" nenalezena v odpovědi GET /branches.')

        branch_id = orlova["id"]
        print(f"Používám pobočku {BRANCH_NAME!r} (id={branch_id}), BASE_URL={BASE_URL!r}")

        for i in range(TOTAL):
            idx = i + 1
            payload = {
                "first_name": FIRST_NAMES[i],
                "last_name": LAST_NAMES[i],
                "age_group": AGE_GROUPS[i % len(AGE_GROUPS)],
                "branch_ids": [branch_id],
                "parents": [
                    {
                        "email": f"orlova-demo-{idx:02d}@example.com",
                        "first_name": PARENT_FIRST[i],
                        "last_name": PARENT_LAST[i],
                        "phone": f"+420601{idx + 1000:06d}",
                    }
                ],
            }
            pr = client.post("/students", json=payload)
            if pr.status_code not in (200, 201):
                _fail(f"POST /students selhalo pro žáka #{idx} ({pr.status_code})", pr)
            body = pr.json()
            print(f"  OK žák id={body.get('id')} — {payload['first_name']} {payload['last_name']}")

    print(f"Hotovo: vytvořeno {TOTAL} žáků na pobočce {BRANCH_NAME}.")


if __name__ == "__main__":
    main()
