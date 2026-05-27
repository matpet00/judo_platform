#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

source .venv/bin/activate
pytest tests/ -q
(cd frontend && npm run build)
python scripts/smoke_attendance_flow.py

echo "All judo-verify checks passed."
