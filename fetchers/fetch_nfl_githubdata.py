#!/usr/bin/env python3
"""
fetch_nfl_githubdata.py — Free NFL data fetcher (public GitHub JSON source)

Pulls weekly team stats and saves to Data/nfl_team_stats.csv.
This uses a free, public dataset mirrored from nflfastR and Pro-Football-Reference.
"""

import os
import pandas as pd
from pathlib import Path
import requests

DATA_DIR = Path("Data")
DATA_DIR.mkdir(exist_ok=True)
OUT_FILE = DATA_DIR / "nfl_team_stats.csv"

def fetch_and_save():
    try:
        print("🏈 Fetching NFL data from GitHub JSON...")
        url = "https://raw.githubusercontent.com/nflverse/nflfastR-data/master/data/team_stats.csv"
        df = pd.read_csv(url)
        df = df[["season", "week", "team", "offense_pass_epa", "offense_rush_epa", "defense_epa", "total_yards", "points_scored"]]
        df.rename(columns={
            "team": "Team",
            "season": "Season",
            "week": "Week",
            "points_scored": "Points"
        }, inplace=True)
        df.to_csv(OUT_FILE, index=False)
        print(f"✅ Saved NFL stats → {OUT_FILE} ({len(df)} rows)")
        return df
    except Exception as e:
        print(f"❌ NFL fetch failed: {e}")
        return pd.DataFrame()

if __name__ == "__main__":
    fetch_and_save()
