#!/usr/bin/env python3
"""
fetch_sportsdata.py — LockBox static passthrough (no API mode)
Uses local Data/team_stats_latest.csv as stats source.
"""

from pathlib import Path
import pandas as pd

DATA_DIR = Path("Data")
OUT_FILE = DATA_DIR / "team_stats_latest.csv"

def fetch_all():
    if OUT_FILE.exists():
        df = pd.read_csv(OUT_FILE)
        print(f"📁 Using static file {OUT_FILE} ({len(df)} rows, {', '.join(df.columns)})")
    else:
        print("❌ Missing Data/team_stats_latest.csv — please upload or commit it.")

if __name__ == "__main__":
    fetch_all()
