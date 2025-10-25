#!/usr/bin/env python3
"""
fetch_all_sports.py — Unified open-data fetcher for LockBox

This script replaces SportsData.io with public-API sources:
  • NFL    → from open GitHub data snapshots
  • NCAAF  → from CollegeFootballData API
  • NBA    → from BallDontLie
  • MLB    → from MLB StatsAPI
  • NHL    → from NHL StatsAPI

Each fetcher in /fetchers outputs a CSV to Data/<sport>_team_stats.csv.
This script then merges them all into one file:
  Data/team_stats_latest.csv
"""

import pandas as pd
from pathlib import Path
import importlib
import sys

DATA_DIR = Path("Data")
DATA_DIR.mkdir(exist_ok=True)
OUT_FILE = DATA_DIR / "team_stats_latest.csv"

FETCHERS = {
    "NFL": "fetchers.fetch_nfl_githubdata",
    "NCAAF": "fetchers.fetch_ncaa_collegefootballdata",
    "NBA": "fetchers.fetch_nba_balldontlie",
    "MLB": "fetchers.fetch_mlb_statsapi",
    "NHL": "fetchers.fetch_nhl_statsapi",
}


def run_fetchers():
    combined = []
    for sport, module_name in FETCHERS.items():
        print(f"📊 Running fetcher for {sport}...")
        try:
            mod = importlib.import_module(module_name)
            if hasattr(mod, "fetch_and_save"):
                df = mod.fetch_and_save(DATA_DIR)
                if df is not None and not df.empty:
                    df["Sport"] = sport
                    combined.append(df)
                    print(f"✅ {sport}: {len(df)} records fetched.")
                else:
                    print(f"⚠️ {sport}: No data returned.")
            else:
                print(f"⚠️ {sport}: Missing fetch_and_save() in {module_name}.")
        except Exception as e:
            print(f"❌ Error running {sport} fetcher: {e}")

    if not combined:
        print("⚠️ No data combined — check API limits or network access.")
        sys.exit(0)

    df_all = pd.concat(combined, ignore_index=True)
    df_all.drop_duplicates(inplace=True)
    df_all.to_csv(OUT_FILE, index=False)
    print(f"🏁 Saved unified dataset → {OUT_FILE} ({len(df_all)} rows)")


if __name__ == "__main__":
    run_fetchers()
