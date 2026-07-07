"""Concurrency / multi-user probe against a RUNNING judo backend.

Simulates many trainers/parents hitting the API at the same time to surface
concurrency issues (SQLite "database is locked", races on unique constraints,
lost updates, dupes). Creates throwaway data tagged ZZ_CC and cleans it up.

Usage:
    .venv/bin/python scripts/concurrency_test.py [--base http://localhost:8001]
"""

from __future__ import annotations

import argparse
import asyncio
import random
import statistics
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta

import httpx

TAG = "ZZ_CC"
N_TRAINERS = 8
N_STUDENTS = 20
N_PARENT_LOGINS = 5


@dataclass
class Result:
    label: str
    status: int
    ms: float
    error: str = ""


@dataclass
class Bag:
    results: list[Result] = field(default_factory=list)

    def add(self, r: Result) -> None:
        self.results.append(r)

    def by_label(self, label: str) -> list[Result]:
        return [r for r in self.results if r.label == label]


async def call(
    client: httpx.AsyncClient,
    bag: Bag,
    label: str,
    method: str,
    path: str,
    *,
    token: str | None = None,
    json: object | None = None,
) -> httpx.Response | None:
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    t0 = time.perf_counter()
    try:
        resp = await client.request(method, path, headers=headers, json=json)
        ms = (time.perf_counter() - t0) * 1000
        err = "" if resp.is_success else resp.text[:180]
        bag.add(Result(label, resp.status_code, ms, err))
        return resp
    except Exception as exc:  # noqa: BLE001
        ms = (time.perf_counter() - t0) * 1000
        bag.add(Result(label, -1, ms, f"{type(exc).__name__}: {exc}"))
        return None


def pct(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    k = min(len(values) - 1, int(round((p / 100) * (len(values) - 1))))
    return values[k]


def summarize(bag: Bag) -> None:
    labels = sorted({r.label for r in bag.results})
    print(f"\n{'scenario/label':38} {'n':>5} {'ok':>5} {'err':>5} {'p50ms':>8} {'p95ms':>8} {'maxms':>8}")
    print("-" * 90)
    locked = 0
    server_errs: Counter[str] = Counter()
    for label in labels:
        rs = bag.by_label(label)
        oks = [r for r in rs if 200 <= r.status < 300]
        errs = [r for r in rs if not (200 <= r.status < 300)]
        ms = [r.ms for r in rs]
        print(
            f"{label:38} {len(rs):>5} {len(oks):>5} {len(errs):>5} "
            f"{pct(ms, 50):>8.1f} {pct(ms, 95):>8.1f} {max(ms) if ms else 0:>8.1f}",
        )
        for r in errs:
            low = r.error.lower()
            if "database is locked" in low or "operationalerror" in low:
                locked += 1
            if r.status >= 500 or r.status == -1:
                server_errs[r.error[:80]] += 1
    print("-" * 90)
    print(f"'database is locked' style errors: {locked}")
    if server_errs:
        print("5xx / transport errors (top):")
        for msg, n in server_errs.most_common(8):
            print(f"  x{n}: {msg}")
    else:
        print("5xx / transport errors: none")


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:8001")
    args = ap.parse_args()

    bag = Bag()
    limits = httpx.Limits(max_connections=100, max_keepalive_connections=50)
    async with httpx.AsyncClient(base_url=args.base, timeout=30.0, limits=limits) as client:
        created = {"trainers": [], "students": [], "group": None, "branch": None, "event": None,
                   "conversation": None, "parents": []}
        try:
            # ---------- SETUP ----------
            print("== SETUP ==")
            r = await call(client, bag, "setup.admin_login", "POST", "/admin/login",
                           json={"username": "admin", "password": "admin"})
            assert r and r.is_success, "admin login failed"
            admin = r.json()["access_token"]

            r = await call(client, bag, "setup.branch", "POST", "/branches", token=admin,
                           json={"name": f"{TAG} Branch {int(time.time())}", "address": "Test 1"})
            assert r and r.is_success, f"branch create failed: {r.text if r else ''}"
            branch_id = r.json()["id"]
            created["branch"] = branch_id

            trainer_tokens: list[str] = []
            trainer_ids: list[int] = []
            for i in range(N_TRAINERS):
                r = await call(client, bag, "setup.trainer", "POST", "/trainers", token=admin,
                               json={"first_name": f"{TAG}T{i}", "last_name": "Trener", "branch_ids": [branch_id]})
                assert r and r.is_success
                tid = r.json()["id"]
                trainer_ids.append(tid)
                await call(client, bag, "setup.trainer_pin", "PATCH", f"/trainers/{tid}", token=admin,
                           json={"pin": "1234"})
                r = await call(client, bag, "setup.verify_pin", "POST", f"/trainers/{tid}/verify-pin",
                               json={"pin": "1234"})
                assert r and r.is_success
                trainer_tokens.append(r.json()["access_token"])
            created["trainers"] = trainer_ids

            student_ids: list[int] = []
            for i in range(N_STUDENTS):
                r = await call(client, bag, "setup.student", "POST", "/students", token=admin, json={
                    "first_name": f"{TAG}S{i}", "last_name": "Dite", "age_group": "U10",
                    "branch_ids": [branch_id],
                    "parents": [{"first_name": f"{TAG}P{i}", "last_name": "Rodic",
                                 "email": f"zzcc_parent_{i}_{int(time.time())}@example.com",
                                 "phone": f"+4206000000{i:02d}"}],
                })
                assert r and r.is_success, f"student failed: {r.text if r else ''}"
                student_ids.append(r.json()["id"])
            created["students"] = student_ids

            today = date.today()
            r = await call(client, bag, "setup.group", "POST", "/training-groups", token=trainer_tokens[0], json={
                "branch_id": branch_id, "name": f"{TAG} Group", "start_time": "17:00:00", "end_time": "18:00:00",
                "weekdays": [today.isoweekday()], "student_ids": student_ids,
            })
            assert r and r.is_success, f"group failed: {r.text if r else ''}"
            group_id = r.json()["id"]
            created["group"] = group_id

            r = await call(client, bag, "setup.session", "POST", f"/training-groups/{group_id}/sessions",
                           token=trainer_tokens[0], json={"session_date": today.isoformat()})
            assert r and r.is_success, f"session failed: {r.text if r else ''}"
            session_id = r.json()["id"]

            print(f"branch={branch_id} trainers={len(trainer_ids)} students={len(student_ids)} "
                  f"group={group_id} session={session_id}")

            # ---------- SCENARIO A: attendance write storm ----------
            print("\n== SCENARIO A: attendance write storm (every trainer marks every student at once) ==")

            async def set_attendance(tok: str, sid: int, stud: int) -> None:
                st = random.choice(["present", "absent", "excused"])
                r = await call(client, bag, "A.attendance_post", "POST",
                               f"/training-sessions/{sid}/attendance", token=tok,
                               json={"student_id": stud, "status": st})
                if r is not None and r.status_code == 409:
                    d = await call(client, bag, "A.session_get", "GET",
                                   f"/training-sessions/{sid}", token=tok)
                    aid = None
                    if d and d.is_success:
                        for s in d.json().get("students", []):
                            if s["id"] == stud and s.get("attendance"):
                                aid = s["attendance"]["id"]
                                break
                    if aid:
                        await call(client, bag, "A.attendance_patch", "PATCH",
                                   f"/training-sessions/{sid}/attendance/{aid}", token=tok,
                                   json={"status": st})

            tasks = [set_attendance(trainer_tokens[t], session_id, stud)
                     for stud in student_ids for t in range(N_TRAINERS)]
            random.shuffle(tasks)
            ta = time.perf_counter()
            await asyncio.gather(*tasks)
            print(f"  {len(tasks)} concurrent attendance ops in {(time.perf_counter()-ta)*1000:.0f} ms")

            # consistency check
            r = await call(client, bag, "A.verify_list", "GET",
                           f"/training-sessions/{session_id}/attendance", token=trainer_tokens[0])
            n_records = len(r.json()) if r and r.is_success else -1
            dupe = "OK" if n_records == len(student_ids) else f"MISMATCH (got {n_records}, expected {len(student_ids)})"
            print(f"  attendance rows after storm: {n_records} -> uniqueness {dupe}")

            # ---------- SCENARIO B: mixed read/write burst ----------
            print("\n== SCENARIO B: mixed reads + notification writes + attendance edits ==")
            from_iso = (today - timedelta(days=7)).isoformat()
            to_iso = (today + timedelta(days=30)).isoformat()
            mixed: list = []
            for t in range(N_TRAINERS):
                mixed.append(call(client, bag, "B.read_occurrences", "GET",
                                  f"/training-groups/occurrences?from={from_iso}&to={to_iso}",
                                  token=trainer_tokens[t]))
                mixed.append(call(client, bag, "B.read_session", "GET",
                                  f"/training-sessions/{session_id}", token=trainer_tokens[t]))
                mixed.append(call(client, bag, "B.notif_create", "POST", "/notifications",
                                  token=trainer_tokens[t], json={
                                      "title": f"{TAG} notif {t}", "body": "concurrency",
                                      "targets": [{"audience": "trainer"}]}))
            for stud in student_ids[:10]:
                mixed.append(set_attendance(trainer_tokens[random.randrange(N_TRAINERS)], session_id, stud))
            random.shuffle(mixed)
            tb = time.perf_counter()
            await asyncio.gather(*mixed)
            print(f"  {len(mixed)} mixed ops in {(time.perf_counter()-tb)*1000:.0f} ms")

            # ---------- SCENARIO C: chat message integrity ----------
            print("\n== SCENARIO C: two trainers spamming one conversation concurrently ==")
            r = await call(client, bag, "C.start_conv", "POST", "/chat/conversations",
                           token=trainer_tokens[0],
                           json={"counterpart_kind": "trainer", "counterpart_id": trainer_ids[1]})
            if r and r.is_success:
                conv_id = r.json()["id"]
                created["conversation"] = conv_id
                N_MSG = 20
                chat_tasks = []
                for k in range(N_MSG):
                    who = 0 if k % 2 == 0 else 1
                    chat_tasks.append(call(client, bag, "C.send", "POST",
                                           f"/chat/conversations/{conv_id}/messages",
                                           token=trainer_tokens[who], json={"body": f"msg {k}"}))
                await asyncio.gather(*chat_tasks)
                r = await call(client, bag, "C.verify", "GET",
                               f"/chat/conversations/{conv_id}/messages", token=trainer_tokens[0])
                got = len(r.json()) if r and r.is_success else -1
                print(f"  sent {N_MSG} concurrent messages -> stored {got} "
                      f"({'OK' if got == N_MSG else 'LOST/DUP'})")
                # remove the conversation so repeated runs stay clean
                await call(client, bag, "C.cleanup", "DELETE",
                           f"/chat/conversations/{conv_id}", token=trainer_tokens[0])

            # ---------- SCENARIO D: RSVP uniqueness under concurrency ----------
            print("\n== SCENARIO D: parents RSVP the same child concurrently (unique constraint) ==")
            starts = (datetime.now(UTC) + timedelta(days=3)).isoformat()
            r = await call(client, bag, "D.event", "POST", "/events", token=trainer_tokens[0], json={
                "title": f"{TAG} Event", "event_type": "tournament", "starts_at": starts,
                "targets": [{"audience": "parent"}]})
            if r and r.is_success:
                event_id = r.json()["id"]
                created["event"] = event_id
                # Get real parent ids + child ids via students list
                sresp = await call(client, bag, "D.students", "GET", "/students", token=admin)
                child_parent = {}
                if sresp and sresp.is_success:
                    for s in sresp.json():
                        if s["id"] in student_ids[:N_PARENT_LOGINS] and s.get("parents"):
                            child_parent[s["id"]] = s["parents"][0]["id"]
                logins = []
                for stud_id, par_id in child_parent.items():
                    rr = await call(client, bag, "D.resend2", "POST",
                                    f"/admin/parents/{par_id}/resend-credentials", token=admin)
                    if rr and rr.is_success:
                        j = rr.json()
                        lg = await call(client, bag, "D.parent_login", "POST", "/parents/login",
                                        json={"username": j["username"], "password": j["password"]})
                        if lg and lg.is_success:
                            logins.append((lg.json()["access_token"], stud_id))
                # Each parent fires 4 concurrent RSVPs for their own child (racing writes on same row).
                rsvp_tasks = []
                for tok, stud_id in logins:
                    for _ in range(4):
                        st = random.choice(["yes", "no", "maybe"])
                        rsvp_tasks.append(call(client, bag, "D.rsvp", "POST",
                                               f"/events/{event_id}/rsvp", token=tok,
                                               json={"responses": [{"student_id": stud_id, "status": st}]}))
                random.shuffle(rsvp_tasks)
                await asyncio.gather(*rsvp_tasks)
                dv = await call(client, bag, "D.verify", "GET", f"/events/{event_id}", token=trainer_tokens[0])
                if dv and dv.is_success:
                    summ = dv.json().get("rsvp_summary") or {}
                    parts = summ.get("participants", [])
                    child_rows = [p for p in parts if p.get("student_id")]
                    ids = [p["student_id"] for p in child_rows]
                    dup = len(ids) != len(set(ids))
                    print(f"  {len(logins)} parents x4 concurrent RSVPs -> {len(child_rows)} child rows, "
                          f"{'DUPLICATE!' if dup else 'unique OK'}")

        finally:
            # ---------- CLEANUP ----------
            print("\n== CLEANUP ==")
            admin_tok = None
            r = await client.post("/admin/login", json={"username": "admin", "password": "admin"})
            if r.is_success:
                admin_tok = r.json()["access_token"]
            h = {"Authorization": f"Bearer {admin_tok}"} if admin_tok else {}
            if created.get("conversation") and created["trainers"]:
                # conversation cleaned by deleting trainers (participants cascade); best effort
                pass
            if created.get("event"):
                await client.delete(f"/events/{created['event']}", headers=h)
            if created.get("group"):
                await client.delete(f"/training-groups/{created['group']}", headers=h)
            for sid in created.get("students", []):
                await client.delete(f"/students/{sid}", headers=h)
            for tid in created.get("trainers", []):
                await client.delete(f"/trainers/{tid}", headers=h)
            # parents left behind get removed via safe delete
            pr = await client.get("/parents", headers=h)
            if pr.is_success:
                for p in pr.json():
                    if str(p.get("last_name")) == "Rodic" and str(p.get("first_name", "")).startswith(TAG):
                        await client.delete(f"/parents/{p['id']}", headers=h)
            if created.get("branch"):
                await client.delete(f"/branches/{created['branch']}", headers=h)
            print("cleanup done")

    summarize(bag)


if __name__ == "__main__":
    asyncio.run(main())
