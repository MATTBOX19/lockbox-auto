#!/usr/bin/env python3
"""
fetch_nfl_githubdata.py — Free NFL data fetcher (nflfastR public repo)

Downloads weekly team-level stats from nflverse/nflfastR-data.
Saves output to Data/nfl_team_stats.csv for LockBox model training.
"""

import os
import pandas as pd
from pathlib import Path

DATA_DIR = Path("Data")
DATA_DIR.mkdir(exist_ok=True)
OUT_FILE = DATA_DIR / "nfl_team_stats.csv"

def fetch_and_save():
    try:
        print("🏈 Fetching NFL team stats from nflfastR (GitHub CSV)...")
        url = "https://raw.githubusercontent.com/nflverse/nflfastR-data/master/data/team_stats/team_stats.csv.gz"
        df = pd.read_csv(url, compression="gzip", low_memory=False)
        # Keep a small subset of columns
        keep = [
            "season", "week", "team", "offense_epa", "defense_epa",
            "offense_pass_epa", "offense_rush_epa",
            "defense_pass_epa", "defense_rush_epa",
            "offense_total_yards", "defense_total_yards",
            "offense_points", "defense_points"
        ]
        df = df[[c for c in keep if c in df.columns]]
        df.rename(columns={"team": "Team"}, inplace=True)
        df.to_csv(OUT_FILE, index=False)
        print(f"✅ Saved NFL stats → {OUT_FILE} ({len(df)} rows)")
        return df
    except Exception as e:
        print(f"❌ NFL fetch failed: {e}")
        return pd.DataFrame()

if __name__ == "__main__":
    fetch_and_save()
