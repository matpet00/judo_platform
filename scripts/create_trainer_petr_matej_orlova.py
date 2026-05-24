#!/usr/bin/env python3
"""Přes REST API vytvoří trenéra Petr Matej na pobočce Orlova.

Nejdřív musí běžet Judo API, např.:

    uvicorn app.main:app --reload --port 8001

Pak z kořene projektu:

    python scripts/create_trainer_petr_matej_orlova.py

Jiný host/port: BASE_URL=http://127.0.0.1:8000 python scripts/create_trainer_petr_matej_orlova.py
"""

from __future__ import annotations

import os
import sys

import httpx

BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8001").rstrip("/")
BRANCH_NAME = "Orlova"
FIRST_NAME = "Petr"
LAST_NAME = "Matej"

_JUDO_HINT = f"""
Zkontroluj:
  1) Z kořene projektu (složka judo) běží: uvicorn app.main:app --reload --port 8001
  2) V prohlížeči {BASE_URL}/docs — titulek „Judo club“
  3) GET {BASE_URL}/health vrací {{"status":"ok"}}
  4) Jiný port: nastav BASE_URL (viz docstring skriptu).
""".strip()


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


def _orlova_branch_id(client: httpx.Client) -> int:
    r = client.get("/branches")
    if r.status_code != 200:
        _fail(
            f"GET /branches selhalo ({r.status_code}).\n{_JUDO_HINT}",
            r,
        )
    branches = r.json()
    orlova = next((b for b in branches if b.get("name") == BRANCH_NAME), None)
    if orlova is None:
        _fail(f'Pobočka "{BRANCH_NAME}" nenalezena v odpovědi GET /branches.')
    return int(orlova["id"])


def _trainer_already_exists(client: httpx.Client, branch_id: int) -> bool:
    r = client.get("/trainers")
    if r.status_code != 200:
        _fail(f"GET /trainers selhalo ({r.status_code})", r)
    for t in r.json():
        if t.get("first_name") != FIRST_NAME or t.get("last_name") != LAST_NAME:
            continue
        for br in t.get("branches") or []:
            if br.get("id") == branch_id and br.get("name") == BRANCH_NAME:
                return True
    return False


def main() -> None:
    with httpx.Client(base_url=BASE_URL, timeout=60.0) as client:
        _expect_judo_health(client)
        branch_id = _orlova_branch_id(client)

        if _trainer_already_exists(client, branch_id):
            print(
                f"Trenér {FIRST_NAME} {LAST_NAME} už u pobočky {BRANCH_NAME!r} existuje — nic nevytvářím.",
            )
            return

        payload = {
            "first_name": FIRST_NAME,
            "last_name": LAST_NAME,
            "branch_ids": [branch_id],
        }
        pr = client.post("/trainers", json=payload)
        if pr.status_code not in (200, 201):
            _fail(f"POST /trainers selhalo ({pr.status_code})", pr)

        body = pr.json()
        print(
            f"Hotovo: trenér id={body.get('id')} — {FIRST_NAME} {LAST_NAME}, "
            f"pobočka {BRANCH_NAME!r} (id={branch_id}), BASE_URL={BASE_URL!r}",
        )


if __name__ == "__main__":
    main()
