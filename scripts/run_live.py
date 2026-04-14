#!/usr/bin/env python3
"""Wrapper to load .env then run the full pipeline test.

Run with: python -u scripts/run_live.py

This script loads environment variables from the repo `.env` (if present)
and then executes `scripts/run_full_test.py` as __main__ so the full test
behaves exactly the same as running the script directly.
"""
from dotenv import load_dotenv
import runpy
import os
from pathlib import Path

# Ensure working directory is the repository root
ROOT = Path(__file__).resolve().parent
os.chdir(str(ROOT.parent))

env_path = ROOT.parent / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=str(env_path))
else:
    print(f"Warning: .env not found at {env_path} — relying on already-set environment variables")

# Execute the existing verbose runner
runpy.run_path(str(ROOT / "run_full_test.py"), run_name="__main__")
