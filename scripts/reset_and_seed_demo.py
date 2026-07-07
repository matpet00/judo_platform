#!/usr/bin/env python3
"""Reset demo data: keep 3 default branches + trainers, wipe children/parents, seed 30 students.

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
ADMIN_USER = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASS = os.environ.get("ADMIN_PASSWORD", "admin")
TRAINER_PIN = os.environ.get("TRAINER_PIN", "1234")
STATE_PATH = os.environ.get("DEMO_STATE_PATH", "scripts/demo_state.json")

KEEP_BRANCHES = ("Orlova", "Dolni Lutyne", "Petrvald")
PER_BRANCH = 10

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
AGE_GROUPS = ("U8", "U10", "U12", "U14", "U16", "U18")
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


def wipe(client: httpx.Client, admin: str, trainer_tok: str) -> None:
    print("== WIPE ==")
    for s in client.get("/students", headers=headers()).json():
        client.delete(f"/students/{s['id']}", headers=headers(admin))

    for p in client.get("/parents", headers=headers()).json():
        client.delete(f"/parents/{p['id']}", headers=headers())

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


def seed_students(client: httpx.Client, branches: dict[str, int]) -> list[dict]:
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
            r = client.post("/students", headers=headers(), json=payload)
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


def seed_trainings_and_event(client: httpx.Client, trainer_tok: str, branches: dict[str, int], students: list[dict]) -> dict:
    print("== SEED TRAININGS + EVENT ==")
    today = date.today()
    weekday = today.isoweekday()
    groups: list[dict] = []

    for branch_name, branch_id in branches.items():
        branch_students = [s["id"] for s in students if s["branch"] == branch_name][:6]
        r = client.post(
            "/training-groups",
            headers=headers(trainer_tok),
            json={
                "branch_id": branch_id,
                "name": f"{branch_name} Úterý+Čtvrtek",
                "start_time": "17:00:00",
                "end_time": "18:30:00",
                "weekdays": [2, 4] if branch_name != "Petrvald" else [weekday],
                "active_from": today.isoformat(),
                "active_until": (today + timedelta(days=365)).isoformat(),
                "student_ids": branch_students,
            },
        )
        r.raise_for_status()
        g = r.json()
        groups.append({"id": g["id"], "branch": branch_name, "student_ids": branch_students})
        print(f"  + group {g['name']} ({len(branch_students)} dětí)")

    starts = (today + timedelta(days=14)).isoformat() + "T10:00:00"
    ev = client.post(
        "/events",
        headers=headers(trainer_tok),
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


def main() -> int:
    with httpx.Client(base_url=BASE_URL, timeout=60.0) as client:
        h = client.get("/health")
        if h.status_code != 200:
            print("API not healthy", file=sys.stderr)
            return 1

        admin = admin_login(client)
        trainers = client.get("/trainers").json()
        if not trainers:
            print("No trainers", file=sys.stderr)
            return 1
        trainer_tok = trainer_login(client, trainers[0]["id"])

        wipe(client, admin, trainer_tok)

        branches_list = client.get("/branches").json()
        branches = {b["name"]: b["id"] for b in branches_list if b["name"] in KEEP_BRANCHES}
        if len(branches) != 3:
            print(f"Expected 3 branches, got {branches}", file=sys.stderr)
            return 1

        students = seed_students(client, branches)
        extras = seed_trainings_and_event(client, trainer_tok, branches, students)

        # Parent credentials for QA
        parent_logins: list[dict] = []
        for s in students[:6]:
            pid = s["parent_id"]
            r = client.post(f"/admin/parents/{pid}/resend-credentials", headers=headers(admin))
            if r.status_code == 200:
                j = r.json()
                parent_logins.append({
                    "parent_id": pid,
                    "student_id": s["id"],
                    "username": j["username"],
                    "password": j["password"],
                })

        state = {
            "base_url": BASE_URL,
            "admin_token_hint": "admin/admin",
            "trainer_id": trainers[0]["id"],
            "trainer_pin": TRAINER_PIN,
            "trainers": [{"id": t["id"], "name": f"{t['first_name']} {t['last_name']}"} for t in trainers],
            "branches": branches,
            "students": students,
            "parent_logins": parent_logins,
            **extras,
            "seeded_at": int(time.time()),
        }
        with open(STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)

        print(f"\nOK: {len(students)} students, {len(trainers)} trainers, 3 branches")
        print(f"State: {STATE_PATH}")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
