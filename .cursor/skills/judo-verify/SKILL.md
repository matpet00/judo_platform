---
name: judo-verify
description: Run judo club test checklist before handing off user-facing changes. Use after frontend attendance, trainer auth, or API session changes in the judo project.
---

# Judo verify

Before telling the user a change is ready, run this checklist.

## Steps

From repo root (`/Users/peter/Desktop/judo` or project root):

```bash
source .venv/bin/activate
pip install -r requirements.txt -q
pytest tests/ -q
cd frontend && npm run build
cd ..
python scripts/smoke_attendance_flow.py
```

Smoke requires backend on `:8001`. If not running, start it and retry smoke only:

```bash
uvicorn app.main:app --port 8001
```

Optional env for smoke (must match backend if `API_WRITE_KEY` is set):

```bash
export API_WRITE_KEY=your-key
export TRAINER_PIN=1234
python scripts/smoke_attendance_flow.py
```

## Report format

Reply with:

- pytest: pass/fail
- frontend build: pass/fail
- smoke: pass/fail/skipped (and why)
- manual note if DB migration needed (`pin_hash` column — restart API once)

## Rules

- Do not hand off if pytest or `npm run build` fails.
- Fix failures and re-run the full checklist.
- Default trainer PIN after migration: `1234`
