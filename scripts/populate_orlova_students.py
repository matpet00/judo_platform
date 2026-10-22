#!/usr/bin/env python3
"""Deprecated — use scripts/reset_and_seed_demo.py (generická jména Dítě/Rodič/Trenér)."""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

print("populate_orlova_students.py je nahrazeno reset_and_seed_demo.py", file=sys.stderr)
sys.argv = [str(Path(__file__).with_name("reset_and_seed_demo.py")), *sys.argv[1:]]
runpy.run_path(str(Path(__file__).with_name("reset_and_seed_demo.py")), run_name="__main__")
