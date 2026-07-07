#!/usr/bin/env python3
"""Smazat všechny notifikace a nasadit malou sadu pro testování příjemců a reakcí."""

from __future__ import annotations

import json
import os
import sys

import httpx

BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8001").rstrip("/")
STATE_PATH = os.environ.get("DEMO_STATE_PATH", "scripts/demo_state.json")
TRAINER_PIN = os.environ.get("TRAINER_PIN", "1234")


def headers(token: str | None = None) -> dict[str, str]:
    h = {"Content-Type": "application/json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def trainer_token(client: httpx.Client, trainer_id: int) -> str:
    r = client.post(f"/trainers/{trainer_id}/verify-pin", json={"pin": TRAINER_PIN})
    r.raise_for_status()
    return r.json()["access_token"]


def parent_token(client: httpx.Client, username: str, password: str) -> str:
    r = client.post("/parents/login", json={"username": username, "password": password})
    r.raise_for_status()
    return r.json()["access_token"]


def wipe_all(client: httpx.Client, trainer_tok: str) -> int:
    """Delete every notification (API only removes ones the trainer may delete)."""
    import sqlite3
    from pathlib import Path

    db_path = Path(os.environ.get("JUDO_DB_PATH", "judo.db"))
    if db_path.is_file():
        conn = sqlite3.connect(db_path)
        cur = conn.execute("SELECT COUNT(*) FROM notifications")
        count = cur.fetchone()[0]
        conn.execute("DELETE FROM notifications")
        conn.commit()
        conn.close()
        return count

    notes = client.get("/notifications", headers=headers(trainer_tok)).json()
    deleted = 0
    for n in notes:
        r = client.delete(f"/notifications/{n['id']}", headers=headers(trainer_tok))
        if r.status_code == 204:
            deleted += 1
    return deleted


def post_trainer(
    client: httpx.Client,
    tok: str,
    *,
    title: str,
    body: str,
    targets: list[dict],
) -> dict:
    r = client.post(
        "/notifications",
        headers=headers(tok),
        json={
            "title": title,
            "body": body,
            "duration_amount": 14,
            "duration_unit": "days",
            "targets": targets,
        },
    )
    r.raise_for_status()
    return r.json()


def post_parent_to_trainers(
    client: httpx.Client,
    tok: str,
    *,
    title: str,
    body: str,
    branch_id: int | None = None,
) -> dict:
    payload: dict = {"title": title, "body": body}
    if branch_id is not None:
        payload["branch_id"] = branch_id
    r = client.post("/notifications/to-trainers", headers=headers(tok), json=payload)
    r.raise_for_status()
    return r.json()


def add_comment(client: httpx.Client, tok: str, notification_id: int, body: str, role: str = "trainer") -> dict:
    r = client.post(
        f"/notifications/{notification_id}/comments",
        headers=headers(tok),
        json={"body": body},
    )
    r.raise_for_status()
    return r.json()


def main() -> int:
    if not os.path.isfile(STATE_PATH):
        print(f"Missing {STATE_PATH}", file=sys.stderr)
        return 1

    state = json.load(open(STATE_PATH, encoding="utf-8"))
    branches = state["branches"]
    orlova = branches["Orlova"]
    lutyne = branches["Dolni Lutyne"]
    parent_logins = state.get("parent_logins") or []
    if len(parent_logins) < 2:
        print("Need parent_logins in demo_state.json", file=sys.stderr)
        return 1

    with httpx.Client(base_url=BASE_URL, timeout=45.0) as client:
        tid = state["trainer_id"]
        tt = trainer_token(client, tid)
        t2_id = state["trainers"][1]["id"] if len(state["trainers"]) > 1 else tid
        t2t = trainer_token(client, t2_id)

        deleted = wipe_all(client, tt)
        print(f"Smazáno {deleted} notifikací")

        created: list[dict] = []

        # 1) Trenér → všichni trenéři (+ reakce druhého trenéra)
        n1 = post_trainer(
            client, tt,
            title="[demo] Schůzka trenérů pátek",
            body="Pátek 18:00 sraz na Orlové — prosím potvrďte účast.",
            targets=[{"audience": "trainer"}],
        )
        add_comment(client, t2t, n1["id"], "Já budu, díky za info.")
        created.append({"id": n1["id"], "label": "trenér→trenéři", "comments": 1})

        # 2) Trenér → všichni rodiče (+ reakce rodiče a odpověď trenéra)
        n2 = post_trainer(
            client, tt,
            title="[demo] Oprava šaten",
            body="Šatny budou ve čtvrtek uzavřené — převlékání v chodbě.",
            targets=[{"audience": "parent"}],
        )
        p1 = parent_logins[0]
        pt1 = parent_token(client, p1["username"], p1["password"])
        add_comment(client, pt1, n2["id"], "Díky, předám dětem.", role="parent")
        add_comment(client, tt, n2["id"], "Super, díky za zpětnou vazbu!")
        created.append({"id": n2["id"], "label": "trenér→rodiče (všichni)", "comments": 2})

        # 3) Trenér → rodiče U10 jen Orlova
        n3 = post_trainer(
            client, tt,
            title="[demo] Turnaj U10 Orlova",
            body="Sraz v sobotu v 8:00 u haly — jen kategorie U10 z Orlové.",
            targets=[{"audience": "parent", "branch_id": orlova, "age_group": "U10"}],
        )
        created.append({"id": n3["id"], "label": "trenér→rodiče U10 @ Orlova", "comments": 0})

        # 4) Trenér → všichni @ Dolni Lutyne (trenéři + rodiče pobočky)
        n4 = post_trainer(
            client, tt,
            title="[demo] Změna času — Dolni Lutyne",
            body="Úterní trénink posunut na 18:00 (platí jen pro tuto pobočku).",
            targets=[
                {"audience": "trainer", "branch_id": lutyne},
                {"audience": "parent", "branch_id": lutyne},
            ],
        )
        p2 = parent_logins[1]
        pt2 = parent_token(client, p2["username"], p2["password"])
        add_comment(client, tt, n4["id"], "Potvrzuji změnu pro Lutyň.")
        created.append({"id": n4["id"], "label": "trenér→Lutyne (trenéři+rodiče)", "comments": 1})

        # 5) Rodič → trenéři (celý klub) + odpověď trenéra
        n5 = post_parent_to_trainers(
            client, pt1,
            title="[demo] Dotaz rodiče",
            body="Může naše dítě chybět příští týden kvůli nemoci?",
        )
        add_comment(client, tt, n5["id"], "Ano, stačí napsat docházku jako nemoc — ozvu se.")
        created.append({"id": n5["id"], "label": "rodič→trenéři", "comments": 1})

        # 6) Rodič → trenéři jen Orlova (bez reakce — k rozkliknutí)
        n6 = post_parent_to_trainers(
            client, pt1,
            title="[demo] Dotaz k pobočce Orlova",
            body="Je možné vyzvednout dítě o 15 min dřív?",
            branch_id=orlova,
        )
        created.append({"id": n6["id"], "label": "rodič→trenéři @ Orlova", "comments": 0})

        state["demo_notifications"] = created
        with open(STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)

        print(f"\nNasazeno {len(created)} notifikací:")
        for row in created:
            print(f"  #{row['id']} {row['label']} ({row['comments']} reakcí)")
        print("\nTip: reakce (💬) uvidíš po rozkliknutí karty notifikace (▼).")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
