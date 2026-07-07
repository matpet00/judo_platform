#!/usr/bin/env python3
"""E2E QA against demo_state.json — run full club flow checks."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, timedelta

import httpx

STATE_PATH = os.environ.get("DEMO_STATE_PATH", "scripts/demo_state.json")
TRAINER_PIN = os.environ.get("TRAINER_PIN", "1234")


class QA:
    def __init__(self, base: str):
        self.client = httpx.Client(base_url=base, timeout=45.0)
        self.passed: list[str] = []
        self.failed: list[str] = []

    def ok(self, name: str) -> None:
        self.passed.append(name)

    def fail(self, name: str, detail: str) -> None:
        self.failed.append(f"{name}: {detail}")

    def check(self, name: str, cond: bool, detail: str = "") -> bool:
        if cond:
            self.ok(name)
            return True
        self.fail(name, detail)
        return False

    def close(self) -> None:
        self.client.close()


def headers(token: str | None = None) -> dict[str, str]:
    h = {"Content-Type": "application/json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def load_state(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def trainer_token(client: httpx.Client, trainer_id: int) -> str:
    r = client.post(f"/trainers/{trainer_id}/verify-pin", json={"pin": TRAINER_PIN})
    r.raise_for_status()
    return r.json()["access_token"]


def parent_token(client: httpx.Client, username: str, password: str) -> str:
    r = client.post("/parents/login", json={"username": username, "password": password})
    r.raise_for_status()
    return r.json()["access_token"]


def admin_token(client: httpx.Client) -> str:
    r = client.post("/admin/login", json={"username": "admin", "password": "admin"})
    r.raise_for_status()
    return r.json()["access_token"]


def run_all(state: dict) -> int:
    qa = QA(state["base_url"])
    c = qa.client
    tid = state["trainer_id"]
    tt = trainer_token(c, tid)
    trainers = state["trainers"]
    t2_id = trainers[1]["id"] if len(trainers) > 1 else tid
    t2 = trainer_token(c, t2_id) if t2_id != tid else tt

    # --- Students / branches ---
    students = c.get("/students").json()
    qa.check("30 students", len(students) == 30, f"got {len(students)}")
    female_names = frozenset({
        "Tereza", "Eliška", "Anna", "Kateřina", "Barbora", "Eva", "Veronika", "Lucie",
        "Markéta", "Jana", "Hana", "Zuzana", "Alena", "Lenka", "Andrea",
    })
    bad_girls = [
        f"{s['first_name']} {s['last_name']}"
        for s in students
        if s["first_name"] in female_names
        and not (s["last_name"].endswith("ová") or s["last_name"].endswith("á") or s["last_name"].endswith("ná"))
    ]
    qa.check("girls have -ová surnames", len(bad_girls) == 0, ", ".join(bad_girls[:5]))
    for bname in ("Orlova", "Dolni Lutyne", "Petrvald"):
        n = sum(1 for s in students if any(br["name"] == bname for br in s["branches"]))
        qa.check(f"10 students @ {bname}", n == 10, f"got {n}")

    qa.check("trainers kept", len(c.get("/trainers").json()) == len(state["trainers"]), "count mismatch")

    # --- Recurring trainings ---
    groups = c.get("/training-groups", headers=headers(tt)).json()
    qa.check("3 calendar groups", len(groups) == 3, f"got {len(groups)}")
    month = f"{date.today().year}-{date.today().month:02d}"
    if groups:
        rep = c.get(f"/training-groups/{groups[0]['id']}/attendance-report?month={month}", headers=headers(tt))
        qa.check("attendance report", rep.status_code == 200, rep.text[:120])

    # --- Session + attendance ---
    if groups:
        gid = groups[0]["id"]
        sess = c.post(
            f"/training-groups/{gid}/sessions",
            headers=headers(tt),
            json={"session_date": date.today().isoformat()},
        )
        if sess.status_code in (200, 201):
            sid = sess.json()["id"]
            roster = groups[0].get("students") or []
            if roster:
                stid = roster[0]["id"]
                att = c.put(
                    f"/training-sessions/{sid}/attendance",
                    headers=headers(tt),
                    json={"records": [{"student_id": stid, "status": "present"}]},
                )
                qa.check("mark attendance", att.status_code == 200, att.text[:120])
                ta = c.post(
                    f"/training-sessions/{sid}/trainer-attendance",
                    headers=headers(tt),
                    json={"trainer_id": tid, "status": "present"},
                )
                qa.check("trainer attendance", ta.status_code in (200, 201, 409), ta.text[:120])

    # --- Event + RSVP ---
    ev_id = state.get("event_id")
    if ev_id and state.get("parent_logins"):
        pl = state["parent_logins"][0]
        pt = parent_token(c, pl["username"], pl["password"])
        rsvp = c.post(
            f"/events/{ev_id}/rsvp",
            headers=headers(pt),
            json={"responses": [{"student_id": pl["student_id"], "status": "yes"}]},
        )
        qa.check("parent RSVP yes", rsvp.status_code == 200, rsvp.text[:120])
        ev = c.get(f"/events/{ev_id}", headers=headers(tt)).json()
        qa.check("event has RSVP summary", bool(ev.get("rsvp_summary")), "missing summary")

    # --- Notifications board ---
    note = c.post(
        "/notifications",
        headers=headers(tt),
        json={
            "title": "QA board post",
            "body": "Test nástěnky pro všechny trenéry.",
            "duration_amount": 7,
            "duration_unit": "days",
            "targets": [{"audience": "trainer"}],
        },
    )
    qa.check("trainer notification", note.status_code == 201, note.text[:120])
    feed = c.get("/notifications", headers=headers(tt)).json()
    qa.check("notification visible", any(n["title"] == "QA board post" for n in feed), "not in feed")

    if state.get("parent_logins"):
        pt = parent_token(c, state["parent_logins"][0]["username"], state["parent_logins"][0]["password"])
        pnote = c.post(
            "/notifications/to-trainers",
            headers=headers(pt),
            json={
                "title": "Zpráva rodiče",
                "body": "Dobrý den, trenéři.",
                "duration_amount": 3,
                "duration_unit": "days",
            },
        )
        qa.check("parent-to-trainers notification", pnote.status_code == 201, pnote.text[:120])

    # --- Chat trainer <-> parent ---
    if state.get("parent_logins"):
        pid = state["parent_logins"][0]["parent_id"]
        conv = c.post(
            "/chat/conversations",
            headers=headers(tt),
            json={"counterpart_kind": "parent", "counterpart_id": pid},
        )
        qa.check("start trainer-parent chat", conv.status_code == 201, conv.text[:120])
        if conv.status_code == 201:
            cid = conv.json()["id"]
            msg = c.post(
                f"/chat/conversations/{cid}/messages",
                headers=headers(tt),
                json={"body": "Ahoj z QA testu"},
            )
            qa.check("trainer sends message", msg.status_code == 201, msg.text[:120])
            pt = parent_token(c, state["parent_logins"][0]["username"], state["parent_logins"][0]["password"])
            inbox = c.get("/chat/conversations", headers=headers(pt)).json()
            qa.check("parent sees chat", len(inbox) >= 1, "empty inbox")

    # --- Chat trainer <-> trainer ---
    if t2_id != tid:
        conv2 = c.post(
            "/chat/conversations",
            headers=headers(tt),
            json={"counterpart_kind": "trainer", "counterpart_id": t2_id},
        )
        qa.check("start trainer-trainer chat", conv2.status_code == 201, conv2.text[:120])

    # --- Chat parent <-> parent (need 2 parent tokens) ---
    if len(state.get("parent_logins", [])) >= 2:
        p1 = state["parent_logins"][0]
        p2 = state["parent_logins"][1]
        t1 = parent_token(c, p1["username"], p1["password"])
        # Parent starts chat with another parent - check API allows
        convp = c.post(
            "/chat/conversations",
            headers=headers(t1),
            json={"counterpart_kind": "parent", "counterpart_id": p2["parent_id"]},
        )
        qa.check("parent-parent chat", convp.status_code == 201, convp.text[:120])

    # --- Admin ---
    at = admin_token(c)
    stats = c.get("/admin/stats", headers=headers(at))
    qa.check("admin stats", stats.status_code == 200 and stats.json().get("students") == 30, stats.text[:80])
    branches = c.get("/branches").json()
    qa.check("3 branches only", len(branches) == 3, f"got {len(branches)}")

    # --- Calendar occurrences ---
    today = date.today()
    occ = c.get(
        f"/training-groups/occurrences?from={today.isoformat()}&to={(today + timedelta(days=30)).isoformat()}",
        headers=headers(tt),
    )
    qa.check("calendar occurrences", occ.status_code == 200 and len(occ.json()) > 0, occ.text[:80])

    qa.close()

    print(f"PASSED ({len(qa.passed)}):")
    for p in qa.passed:
        print(f"  ✓ {p}")
    if qa.failed:
        print(f"FAILED ({len(qa.failed)}):")
        for f in qa.failed:
            print(f"  ✗ {f}")
        return 1
    print(f"\nALL {len(qa.passed)} CHECKS PASSED")
    return 0


def run_area(state: dict, area: str) -> int:
    """Run a single QA area (for parallel agents)."""
    qa = QA(state["base_url"])
    c = qa.client
    tid = state["trainer_id"]
    tt = trainer_token(c, tid)

    if area == "students":
        students = c.get("/students").json()
        qa.check("30 students", len(students) == 30, str(len(students)))
        for b in ("Orlova", "Dolni Lutyne", "Petrvald"):
            n = sum(1 for s in students if any(br["name"] == b for br in s["branches"]))
            qa.check(f"10 @ {b}", n == 10, str(n))
    elif area == "trainings":
        groups = c.get("/training-groups", headers=headers(tt)).json()
        qa.check("3 groups", len(groups) == 3, str(len(groups)))
        month = f"{date.today().year}-{date.today().month:02d}"
        if groups:
            r = c.get(f"/training-groups/{groups[0]['id']}/attendance-report?month={month}", headers=headers(tt))
            qa.check("monthly report", r.status_code == 200, r.text[:100])
            occ = c.get(
                f"/training-groups/occurrences?from={date.today().isoformat()}&to={(date.today() + timedelta(days=30)).isoformat()}",
                headers=headers(tt),
            )
            qa.check("occurrences", occ.status_code == 200 and len(occ.json()) > 0, str(len(occ.json()) if occ.is_success else occ.text))
    elif area == "attendance":
        groups = c.get("/training-groups", headers=headers(tt)).json()
        if groups:
            gid = groups[0]["id"]
            sess = c.post(f"/training-groups/{gid}/sessions", headers=headers(tt), json={"session_date": date.today().isoformat()})
            qa.check("open session", sess.status_code in (200, 201), sess.text[:100])
            if sess.is_success:
                sid = sess.json()["id"]
                st = (groups[0].get("students") or [{}])[0].get("id")
                if st:
                    att = c.put(f"/training-sessions/{sid}/attendance", headers=headers(tt), json={"records": [{"student_id": st, "status": "present"}]})
                    qa.check("student attendance", att.status_code == 200, att.text[:100])
                ta = c.post(f"/training-sessions/{sid}/trainer-attendance", headers=headers(tt), json={"trainer_id": tid, "status": "present"})
                qa.check("trainer on session", ta.status_code in (200, 201, 409), ta.text[:100])
    elif area == "events":
        ev_id = state.get("event_id")
        if ev_id and state.get("parent_logins"):
            pl = state["parent_logins"][0]
            pt = parent_token(c, pl["username"], pl["password"])
            r = c.post(f"/events/{ev_id}/rsvp", headers=headers(pt), json={"responses": [{"student_id": pl["student_id"], "status": "yes"}]})
            qa.check("RSVP", r.status_code == 200, r.text[:100])
    elif area == "notifications":
        n = c.post("/notifications", headers=headers(tt), json={"title": f"QA {area}", "body": "test", "duration_amount": 7, "duration_unit": "days", "targets": [{"audience": "trainer"}]})
        qa.check("post notification", n.status_code == 201, n.text[:100])
        feed = c.get("/notifications", headers=headers(tt)).json()
        qa.check("feed has post", any(x["title"] == f"QA {area}" for x in feed), "missing")
    elif area == "chat_trainer_parent":
        if state.get("parent_logins"):
            pid = state["parent_logins"][0]["parent_id"]
            conv = c.post("/chat/conversations", headers=headers(tt), json={"counterpart_kind": "parent", "counterpart_id": pid})
            qa.check("conversation", conv.status_code == 201, conv.text[:100])
            if conv.is_success:
                cid = conv.json()["id"]
                m = c.post(f"/chat/conversations/{cid}/messages", headers=headers(tt), json={"body": "test"})
                qa.check("message", m.status_code == 201, m.text[:100])
    elif area == "chat_trainers":
        trainers = state["trainers"]
        if len(trainers) > 1:
            t2 = trainers[1]["id"]
            t2t = trainer_token(c, t2)
            conv = c.post("/chat/conversations", headers=headers(tt), json={"counterpart_kind": "trainer", "counterpart_id": t2})
            qa.check("trainer-trainer conv", conv.status_code == 201, conv.text[:100])
            if conv.is_success:
                m = c.post(f"/chat/conversations/{conv.json()['id']}/messages", headers=headers(t2t), json={"body": "ahoj kolego"})
                qa.check("trainer message", m.status_code == 201, m.text[:100])
    elif area == "chat_parents":
        pls = state.get("parent_logins", [])
        if len(pls) >= 2:
            t1 = parent_token(c, pls[0]["username"], pls[0]["password"])
            conv = c.post("/chat/conversations", headers=headers(t1), json={"counterpart_kind": "parent", "counterpart_id": pls[1]["parent_id"]})
            qa.check("parent-parent conv", conv.status_code == 201, conv.text[:100])
    elif area == "admin":
        at = admin_token(c)
        s = c.get("/admin/stats", headers=headers(at))
        qa.check("stats", s.status_code == 200 and s.json().get("students") == 30, s.text[:80])
        qa.check("3 branches", len(c.get("/branches").json()) == 3, "")
    else:
        qa.fail(area, "unknown area")
    qa.close()
    failed = qa.failed
    print(f"[{area}] {len(qa.passed)} pass, {len(failed)} fail")
    for f in failed:
        print(f"  FAIL {f}")
    return 1 if failed else 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--area", default="all", help="all|students|trainings|attendance|events|notifications|chat_*|admin")
    parser.add_argument("--state", default=STATE_PATH)
    args = parser.parse_args()
    if not os.path.isfile(args.state):
        print(f"Missing {args.state} — run reset_and_seed_demo.py first", file=sys.stderr)
        return 1
    state = load_state(args.state)
    if args.area == "all":
        return run_all(state)
    return run_area(state, args.area)


if __name__ == "__main__":
    raise SystemExit(main())
