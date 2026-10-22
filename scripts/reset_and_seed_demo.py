#!/usr/bin/env python3
"""Reset demo data: trainers, students, trainings, notifications, chat, today's attendance.

Usage (API on :8001):
    python scripts/reset_and_seed_demo.py
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import date, timedelta

import httpx

BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8001").rstrip("/")
API_WRITE_KEY = os.environ.get("API_WRITE_KEY", "")
ADMIN_USER = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASS = os.environ.get("ADMIN_PASSWORD", "admin")
TRAINER_PIN = os.environ.get("TRAINER_PIN", "123456")
STATE_PATH = os.environ.get("DEMO_STATE_PATH", "scripts/demo_state.json")

KEEP_BRANCHES = ("Orlova", "Dolni Lutyne", "Petrvald")
PER_BRANCH = 10

# Všichni trenéři z lokální demo DB (idempotentně doplní chybějící přes API)
DEMO_TRAINERS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("Petr", "Matejcek", ("Orlova",)),
    ("Tomas", "Sikora", ("Orlova",)),
    ("Tomas", "Heczko", ("Orlova",)),
    ("Viki", "Fintová", ("Orlova",)),
    ("Tobias", "Mec", ("Orlova",)),
    ("Lukáš", "Morcin", ("Orlova",)),
    ("Eduard", "Lanča", ("Dolni Lutyne", "Orlova")),
    ("Roman", "Bielczyk", ("Orlova", "Dolni Lutyne")),
    ("Petr", "Steiniger", ("Petrvald",)),
)

FIRST_NAMES = (
    "Tereza", "Jan", "Eliška", "Matěj", "Anna", "Jakub", "Kateřina", "Lukáš", "Barbora", "Martin",
    "Eva", "Ondřej", "Veronika", "Petr", "Lucie", "Michal", "Markéta", "David", "Jana", "Filip",
    "Hana", "Pavel", "Zuzana", "Daniel", "Alena", "Radek", "Lenka", "Václav", "Andrea", "Jiří",
)
LAST_NAMES = (
    "Novák", "Svoboda", "Novotný", "Dvořák", "Černý", "Procházka", "Kučera", "Veselý", "Horák", "Mareš",
    "Pospíšil", "Hájek", "Jelínek", "Urban", "Blažek", "Krejčí", "Holub", "Soukup", "Polák", "Staněk",
    "Beneš", "Šimek", "Moravec", "Navrátil", "Tůma", "Kadlec", "Bartoš", "Pečka", "Čermák", "Sedláček",
)
FEMALE_FIRST_NAMES = frozenset({
    "Tereza", "Eliška", "Anna", "Kateřina", "Barbora", "Eva", "Veronika", "Lucie",
    "Markéta", "Jana", "Hana", "Zuzana", "Alena", "Lenka", "Andrea",
})
FEMININE_LAST_NAMES = {
    "Novák": "Nováková",
    "Svoboda": "Svobodová",
    "Novotný": "Novotná",
    "Dvořák": "Dvořáková",
    "Černý": "Černá",
    "Procházka": "Procházková",
    "Kučera": "Kučerová",
    "Veselý": "Veselá",
    "Horák": "Horáková",
    "Mareš": "Marešová",
    "Pospíšil": "Pospíšilová",
    "Hájek": "Hájková",
    "Jelínek": "Jelínková",
    "Urban": "Urbanová",
    "Blažek": "Blažková",
    "Krejčí": "Krejčová",
    "Holub": "Holubová",
    "Soukup": "Soukupová",
    "Polák": "Poláková",
    "Staněk": "Staňková",
    "Beneš": "Benešová",
    "Šimek": "Šimková",
    "Moravec": "Moravcová",
    "Navrátil": "Navrátilová",
    "Tůma": "Tůmová",
    "Kadlec": "Kadlecová",
    "Bartoš": "Bartošová",
    "Pečka": "Pečková",
    "Čermák": "Čermáková",
    "Sedláček": "Sedláčková",
}


def student_last_name(i: int) -> str:
    base = LAST_NAMES[i]
    if FIRST_NAMES[i] in FEMALE_FIRST_NAMES:
        return FEMININE_LAST_NAMES[base]
    return base
AGE_GROUPS = ("U8", "U10", "U12", "U14", "U16", "U18", "U21", "Over21")
PARENT_FIRST = (
    "Marie", "Petr", "Jana", "Tomáš", "Eva", "Martin", "Lenka", "Pavel", "Hana", "Ondřej",
    "Kateřina", "Michal", "Veronika", "David", "Lucie", "Filip", "Markéta", "Jakub", "Barbora", "Lukáš",
    "Anna", "Radek", "Zuzana", "Daniel", "Alena", "Jiří", "Tereza", "Jan", "Eliška", "Matěj",
)
PARENT_LAST = (
    "Svobodová", "Novák", "Dvořáková", "Černý", "Horáková", "Veselý", "Kučerová", "Procházka", "Benešová", "Mareš",
    "Jelínková", "Urban", "Pospíšilová", "Hájek", "Novotná", "Holub", "Krejčíová", "Staněk", "Moravcová", "Navrátil",
    "Šimková", "Tůma", "Kadlecová", "Bartoš", "Pečková", "Sedláček", "Čermáková", "Bláhová", "Polák", "Soukupová",
)


def headers(token: str | None = None) -> dict[str, str]:
    h = {"Content-Type": "application/json"}
    if API_WRITE_KEY:
        h["X-API-Key"] = API_WRITE_KEY
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def admin_login(client: httpx.Client) -> str:
    r = client.post("/admin/login", json={"username": ADMIN_USER, "password": ADMIN_PASS})
    r.raise_for_status()
    return r.json()["access_token"]


def trainer_login(client: httpx.Client, trainer_id: int) -> str:
    r = client.post(f"/trainers/{trainer_id}/verify-pin", json={"pin": TRAINER_PIN})
    r.raise_for_status()
    return r.json()["access_token"]


def parent_login(client: httpx.Client, username: str, password: str) -> str:
    r = client.post("/parents/login", json={"username": username, "password": password})
    r.raise_for_status()
    return r.json()["access_token"]


def trainer_by_name(trainers: list[dict], first_name: str, last_name: str) -> dict:
    for trainer in trainers:
        if trainer["first_name"] == first_name and trainer["last_name"] == last_name:
            return trainer
    raise RuntimeError(f"Trainer not found: {first_name} {last_name}")


def ensure_trainers(client: httpx.Client, branches: dict[str, int], admin: str) -> list[dict]:
    print("== ENSURE TRAINERS ==")
    existing = client.get("/trainers", headers=headers()).json()
    by_name = {(t["first_name"], t["last_name"]): t for t in existing}
    trainers: list[dict] = []

    for first_name, last_name, branch_names in DEMO_TRAINERS:
        branch_ids = [branches[name] for name in branch_names if name in branches]
        key = (first_name, last_name)
        row = by_name.get(key)
        if row is None:
            r = client.post(
                "/trainers",
                headers=headers(admin),
                json={"first_name": first_name, "last_name": last_name, "branch_ids": branch_ids},
            )
            r.raise_for_status()
            row = r.json()
            print(f"  + {first_name} {last_name}")
        else:
            current_ids = sorted(b["id"] for b in row["branches"])
            if sorted(branch_ids) != current_ids:
                r = client.patch(
                    f"/trainers/{row['id']}",
                    headers=headers(admin),
                    json={"branch_ids": branch_ids},
                )
                r.raise_for_status()
                row = r.json()
                print(f"  ~ {first_name} {last_name} (pobočky)")
            else:
                print(f"  = {first_name} {last_name}")
        client.patch(
            f"/trainers/{row['id']}",
            headers=headers(admin),
            json={"pin": TRAINER_PIN},
        ).raise_for_status()
        trainers.append(row)

    return trainers


def wipe(client: httpx.Client, admin: str, trainer_tok: str) -> None:
    print("== WIPE ==")
    for s in client.get("/students", headers=headers(admin)).json():
        client.delete(f"/students/{s['id']}", headers=headers(admin))

    for p in client.get("/parents", headers=headers(admin)).json():
        client.delete(f"/parents/{p['id']}", headers=headers(admin))

    for g in client.get("/training-groups", headers=headers(trainer_tok)).json():
        client.delete(f"/training-groups/{g['id']}", headers=headers(trainer_tok))

    for e in client.get("/events", headers=headers(trainer_tok)).json():
        client.delete(f"/events/{e['id']}", headers=headers(trainer_tok))

    for n in client.get("/notifications", headers=headers(trainer_tok)).json():
        client.delete(f"/notifications/{n['id']}", headers=headers(trainer_tok))

    for c in client.get("/chat/conversations", headers=headers(trainer_tok)).json():
        client.delete(f"/chat/conversations/{c['id']}", headers=headers(trainer_tok))

    branches = client.get("/branches").json()
    keep_ids = {b["id"] for b in branches if b["name"] in KEEP_BRANCHES}
    for b in branches:
        if b["id"] not in keep_ids:
            client.delete(f"/branches/{b['id']}", headers=headers(admin))


def seed_students(client: httpx.Client, branches: dict[str, int], admin: str) -> list[dict]:
    print("== SEED 30 STUDENTS ==")
    created: list[dict] = []
    idx = 0
    for branch_name in KEEP_BRANCHES:
        branch_id = branches[branch_name]
        for local in range(PER_BRANCH):
            i = idx
            payload = {
                "first_name": FIRST_NAMES[i],
                "last_name": student_last_name(i),
                "age_group": AGE_GROUPS[i % len(AGE_GROUPS)],
                "branch_ids": [branch_id],
                "parents": [{
                    "first_name": PARENT_FIRST[i],
                    "last_name": PARENT_LAST[i],
                    "email": f"demo.{branch_name.lower().replace(' ', '_')}.{local + 1}@example.com",
                    "phone": f"+420700{i:07d}",
                }],
            }
            r = client.post("/students", headers=headers(admin), json=payload)
            r.raise_for_status()
            row = r.json()
            created.append({
                "id": row["id"],
                "name": f"{row['first_name']} {row['last_name']}",
                "branch": branch_name,
                "branch_id": branch_id,
                "parent_id": row["parents"][0]["id"],
                "parent_email": payload["parents"][0]["email"],
            })
            idx += 1
            print(f"  + {row['first_name']} {row['last_name']} @ {branch_name}")
    return created


def trainer_for_branch(trainers: list[dict], branch_name: str) -> dict:
    for trainer in trainers:
        names = {b["name"] for b in trainer["branches"]}
        if branch_name in names:
            return trainer
    raise RuntimeError(f"No trainer for branch {branch_name!r}")


def seed_trainings_and_event(
    client: httpx.Client,
    trainers: list[dict],
    branches: dict[str, int],
    students: list[dict],
) -> dict:
    print("== SEED TRAININGS + EVENT ==")
    today = date.today()
    weekday = today.isoweekday()
    groups: list[dict] = []
    event_trainer_tok: str | None = None

    for branch_name, branch_id in branches.items():
        branch_trainer = trainer_for_branch(trainers, branch_name)
        branch_tok = trainer_login(client, branch_trainer["id"])
        if event_trainer_tok is None:
            event_trainer_tok = branch_tok
        branch_students = [s["id"] for s in students if s["branch"] == branch_name][:6]
        r = client.post(
            "/training-groups",
            headers=headers(branch_tok),
            json={
                "branch_id": branch_id,
                "name": f"{branch_name} Úterý+Čtvrtek",
                "start_time": "17:00:00",
                "end_time": "18:30:00",
                "weekdays": sorted({2, 4, weekday}),
                "active_from": today.isoformat(),
                "active_until": (today + timedelta(days=365)).isoformat(),
                "student_ids": branch_students,
            },
        )
        if r.status_code == 409:
            existing = client.get("/training-groups", headers=headers(branch_tok)).json()
            g = next((row for row in existing if row["name"] == f"{branch_name} Úterý+Čtvrtek"), None)
            if g is None:
                r.raise_for_status()
        else:
            r.raise_for_status()
            g = r.json()
        groups.append({"id": g["id"], "branch": branch_name, "student_ids": branch_students})
        print(f"  + group {g['name']} ({len(branch_students)} dětí)")

    starts = (today + timedelta(days=14)).isoformat() + "T10:00:00"
    ev = client.post(
        "/events",
        headers=headers(event_trainer_tok or trainer_login(client, trainers[0]["id"])),
        json={
            "title": "Jarní turnaj klubu",
            "event_type": "tournament",
            "starts_at": starts,
            "location": "Orlova",
            "targets": [{"audience": "parent"}, {"audience": "trainer"}],
        },
    )
    ev.raise_for_status()
    event_id = ev.json()["id"]
    print(f"  + event id={event_id}")

    return {"groups": groups, "event_id": event_id}


def seed_notifications(
    client: httpx.Client,
    trainers: list[dict],
    branches: dict[str, int],
    parent_logins: list[dict],
) -> list[dict]:
    print("== SEED NOTIFICATIONS ==")
    if len(parent_logins) < 2:
        print("  skip (need parent_logins)")
        return []

    viki = trainer_by_name(trainers, "Viki", "Fintová")
    tomas = trainer_by_name(trainers, "Tomas", "Sikora")
    viki_tok = trainer_login(client, viki["id"])
    tomas_tok = trainer_login(client, tomas["id"])
    orlova = branches["Orlova"]
    lutyne = branches["Dolni Lutyne"]
    p1 = parent_logins[0]
    p2 = parent_logins[1]
    pt1 = parent_login(client, p1["username"], p1["password"])
    pt2 = parent_login(client, p2["username"], p2["password"])
    created: list[dict] = []

    def post_trainer(tok: str, title: str, body: str, targets: list[dict]) -> dict:
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

    def post_parent(tok: str, title: str, body: str, branch_id: int | None = None) -> dict:
        payload: dict = {"title": title, "body": body}
        if branch_id is not None:
            payload["branch_id"] = branch_id
        r = client.post("/notifications/to-trainers", headers=headers(tok), json=payload)
        r.raise_for_status()
        return r.json()

    def comment(tok: str, notification_id: int, body: str) -> None:
        client.post(
            f"/notifications/{notification_id}/comments",
            headers=headers(tok),
            json={"body": body},
        ).raise_for_status()

    n1 = post_trainer(
        viki_tok,
        "[demo] Schůzka trenérů pátek",
        "Pátek 18:00 sraz na Orlové — prosím potvrďte účast.",
        [{"audience": "trainer"}],
    )
    comment(tomas_tok, n1["id"], "Já budu, díky za info.")
    created.append({"id": n1["id"], "label": "trenér→trenéři", "comments": 1})

    n2 = post_trainer(
        viki_tok,
        "[demo] Oprava šaten",
        "Šatny budou ve čtvrtek uzavřené — převlékání v chodbě.",
        [{"audience": "parent"}],
    )
    comment(pt1, n2["id"], "Díky, předám dětem.")
    comment(viki_tok, n2["id"], "Super, díky za zpětnou vazbu!")
    created.append({"id": n2["id"], "label": "trenér→rodiče (všichni)", "comments": 2})

    n3 = post_trainer(
        viki_tok,
        "[demo] Turnaj U10 Orlova",
        "Sraz v sobotu v 8:00 u haly — jen kategorie U10 z Orlové.",
        [{"audience": "parent", "branch_id": orlova, "age_group": "U10"}],
    )
    created.append({"id": n3["id"], "label": "trenér→rodiče U10 @ Orlova", "comments": 0})

    n4 = post_trainer(
        viki_tok,
        "[demo] Změna času — Dolni Lutyne",
        "Úterní trénink posunut na 18:00 (platí jen pro tuto pobočku).",
        [
            {"audience": "trainer", "branch_id": lutyne},
            {"audience": "parent", "branch_id": lutyne},
        ],
    )
    comment(viki_tok, n4["id"], "Potvrzuji změnu pro Lutyň.")
    created.append({"id": n4["id"], "label": "trenér→Lutyne (trenéři+rodiče)", "comments": 1})

    n5 = post_parent(pt1, "[demo] Dotaz rodiče", "Může naše dítě chybět příští týden kvůli nemoci?")
    comment(viki_tok, n5["id"], "Ano, stačí napsat docházku jako nemoc — ozvu se.")
    created.append({"id": n5["id"], "label": "rodič→trenéři", "comments": 1})

    n6 = post_parent(
        pt1,
        "[demo] Dotaz k pobočce Orlova",
        "Je možné vyzvednout dítě o 15 min dřív?",
        branch_id=orlova,
    )
    created.append({"id": n6["id"], "label": "rodič→trenéři @ Orlova", "comments": 0})

    for row in created:
        print(f"  + #{row['id']} {row['label']}")
    return created


def seed_chat(
    client: httpx.Client,
    trainers: list[dict],
    parent_logins: list[dict],
) -> list[dict]:
    print("== SEED CHAT ==")
    if len(parent_logins) < 2:
        print("  skip (need parent_logins)")
        return []

    viki = trainer_by_name(trainers, "Viki", "Fintová")
    tomas = trainer_by_name(trainers, "Tomas", "Sikora")
    viki_tok = trainer_login(client, viki["id"])
    tomas_tok = trainer_login(client, tomas["id"])
    p1 = parent_logins[0]
    p2 = parent_logins[1]
    pt1 = parent_login(client, p1["username"], p1["password"])
    pt2 = parent_login(client, p2["username"], p2["password"])
    created: list[dict] = []

    def start(tok: str, kind: str, counterpart_id: int) -> dict:
        r = client.post(
            "/chat/conversations",
            headers=headers(tok),
            json={"counterpart_kind": kind, "counterpart_id": counterpart_id},
        )
        r.raise_for_status()
        return r.json()

    def send(tok: str, conversation_id: int, body: str) -> None:
        client.post(
            f"/chat/conversations/{conversation_id}/messages",
            headers=headers(tok),
            json={"body": body},
        ).raise_for_status()

    conv_tp = start(viki_tok, "parent", p1["parent_id"])
    send(viki_tok, conv_tp["id"], "Ahoj, prosím doneste souhlas s výjezdem do pátku.")
    send(pt1, conv_tp["id"], "Dobře, pošlu ho zítra emailem.")
    send(viki_tok, conv_tp["id"], "Díky!")
    created.append({"id": conv_tp["id"], "label": "Viki ↔ rodič Tereza", "messages": 3})

    conv_tt = start(viki_tok, "trainer", tomas["id"])
    send(viki_tok, conv_tt["id"], "Ahoj, zítra přebíráš Orlovou?")
    send(tomas_tok, conv_tt["id"], "Jo, budu tam od 17h.")
    created.append({"id": conv_tt["id"], "label": "Viki ↔ Tomas", "messages": 2})

    conv_pp = start(pt1, "parent", p2["parent_id"])
    send(pt1, conv_pp["id"], "Ahoj, víš už program turnaje na sobotu?")
    send(pt2, conv_pp["id"], "Zatím ne, čekám na zprávu od trenéra.")
    created.append({"id": conv_pp["id"], "label": "rodič ↔ rodič", "messages": 2})

    for row in created:
        print(f"  + #{row['id']} {row['label']}")
    return created


def seed_today_sessions(
    client: httpx.Client,
    trainers: list[dict],
    groups: list[dict],
) -> list[dict]:
    print("== SEED TODAY SESSIONS ==")
    today = date.today().isoformat()
    statuses = ("present", "present", "present", "absent", "excused", "present")
    opened: list[dict] = []

    for group in groups:
        branch_name = group["branch"]
        branch_trainer = trainer_for_branch(trainers, branch_name)
        tok = trainer_login(client, branch_trainer["id"])
        r = client.post(
            f"/training-groups/{group['id']}/sessions",
            headers=headers(tok),
            json={"session_date": today, "trainer_id": branch_trainer["id"]},
        )
        if r.status_code not in (200, 201):
            r.raise_for_status()
        session = r.json()
        records = [
            {"student_id": sid, "status": statuses[i % len(statuses)]}
            for i, sid in enumerate(group["student_ids"])
        ]
        if records:
            client.put(
                f"/training-sessions/{session['id']}/attendance",
                headers=headers(tok),
                json={"records": records},
            ).raise_for_status()
        client.post(
            f"/training-sessions/{session['id']}/trainer-attendance",
            headers=headers(tok),
            json={"trainer_id": branch_trainer["id"], "status": "present"},
        ).raise_for_status()
        opened.append({
            "id": session["id"],
            "group_id": group["id"],
            "branch": branch_name,
            "date": today,
            "attendance_marked": len(records),
        })
        print(f"  + session #{session['id']} @ {branch_name} ({len(records)} docházek)")

    return opened


def assign_demo_parent_logins(students: list[dict]) -> list[dict]:
    """Set known demo username/password for seeded parents via local DB."""
    import asyncio
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from sqlalchemy import select

    from app.database import async_session_maker
    from app.models import Parent
    from app.security import hash_pin

    password = os.environ.get("DEMO_PARENT_PASSWORD", "demo1234")
    logins: list[dict] = []

    async def _run() -> None:
        async with async_session_maker() as session:
            for i, s in enumerate(students):
                parent = (
                    await session.execute(select(Parent).where(Parent.id == s["parent_id"]))
                ).scalar_one()
                username = f"demo{i + 1}"
                parent.username = username
                parent.password_hash = hash_pin(password)
                logins.append({
                    "parent_id": parent.id,
                    "student_id": s["id"],
                    "username": username,
                    "password": password,
                })
            await session.commit()

    asyncio.run(_run())
    print(f"== PARENT LOGINS == ({len(logins)} accounts, password={password!r})")
    for row in logins:
        print(f"  {row['username']} / {row['password']} (parent #{row['parent_id']})")
    return logins


def main() -> int:
    with httpx.Client(base_url=BASE_URL, timeout=60.0) as client:
        h = client.get("/health")
        if h.status_code != 200:
            print("API not healthy", file=sys.stderr)
            return 1

        admin = admin_login(client)

        branches_list = client.get("/branches").json()
        branches = {b["name"]: b["id"] for b in branches_list if b["name"] in KEEP_BRANCHES}
        if len(branches) != 3:
            print(f"Expected 3 branches, got {branches}", file=sys.stderr)
            return 1

        trainers = ensure_trainers(client, branches, admin)
        if not trainers:
            print("No trainers", file=sys.stderr)
            return 1
        trainer_tok = trainer_login(client, trainers[0]["id"])

        wipe(client, admin, trainer_tok)

        students = seed_students(client, branches, admin)
        extras = seed_trainings_and_event(client, trainers, branches, students)

        # Parent credentials for QA (API už nevrací plaintext heslo — nastavíme lokálně)
        parent_logins = assign_demo_parent_logins(students[:6])

        demo_notifications = seed_notifications(client, trainers, branches, parent_logins)
        demo_chat = seed_chat(client, trainers, parent_logins)
        demo_sessions = seed_today_sessions(client, trainers, extras["groups"])

        state = {
            "base_url": BASE_URL,
            "admin_token_hint": "admin/admin",
            "trainer_id": trainer_by_name(trainers, "Viki", "Fintová")["id"],
            "trainer_pin": TRAINER_PIN,
            "trainers": [{"id": t["id"], "name": f"{t['first_name']} {t['last_name']}"} for t in trainers],
            "branches": branches,
            "students": students,
            "parent_logins": parent_logins,
            "demo_notifications": demo_notifications,
            "demo_chat": demo_chat,
            "demo_sessions": demo_sessions,
            **extras,
            "seeded_at": int(time.time()),
        }
        with open(STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)

        print(
            f"\nOK: {len(students)} students, {len(trainers)} trainers, "
            f"{len(demo_notifications)} notifications, {len(demo_chat)} chats, "
            f"{len(demo_sessions)} sessions",
        )
        print(f"State: {STATE_PATH}")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
