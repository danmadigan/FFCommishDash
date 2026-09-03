"""Local, file-based storage for payment tracking.

ESPN has no concept of league dues, so who's-paid state lives entirely
on your machine as small JSON files (one per league/season).
"""
import json
from pathlib import Path

STORAGE_DIR = Path("payments")
STORAGE_DIR.mkdir(exist_ok=True)


def _payment_path(league_id, year):
    return STORAGE_DIR / f"payments_{league_id}_{year}.json"


def load_payments(league_id, year):
    path = _payment_path(league_id, year)
    if path.exists():
        with open(path, "r") as f:
            return json.load(f)
    return {}


def save_payments(league_id, year, payments):
    path = _payment_path(league_id, year)
    with open(path, "w") as f:
        json.dump(payments, f, indent=2)
