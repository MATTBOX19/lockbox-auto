#!/usr/bin/env python3
"""
fetch_apisports_stats.py — Unified team stats fetcher using API-Sports

Fetches current season team stats for NFL, NCAAF, NBA, MLB, and NHL
via https://www.api-sports.io/. Requires APISPORTS_KEY environment variable.

Outputs:
  Data/<league>_team_stats.csv
  Data/team_stats_latest.csv (unified file for model training)
"""

import os
import requests
import pandas as pd
from pathlib import Path

API_KEY = os.getenv("APISPORTS_KEY")
if not API_KEY:
    raise SystemExit("❌ Missing APISPORTS_KEY environment variable")

DATA_DIR = Path("Data")
DATA_DIR.mkdir(exist_ok=True)

OUT_FILE = DATA_DIR / "team_stats_latest.csv"

SPORTS = {
    "NFL": {"url": "https://v1.american-football.api-sports.io/teams", "id": "american-football"},
    "NCAAF": {"url": "https://v1.american-football.api-sports.io/teams", "id": "american-football"},
    "NBA": {"url": "https://v1.basketball.api-sports.io/teams", "id": "basketball"},
    "MLB": {"url": "https://v1.baseball.api-sports.io/teams", "id": "baseball"},
    "NHL": {"url": "https://v1.hockey.api-sports.io/teams", "id": "hockey"},
}

HEADERS = {"x-apisports-key": API_KEY}


def fetch_league(league_name: str, config: dict) -> pd.DataFrame:
    print(f"📊 Fetching {league_name} team data...")
    try:
        response = requests.get(config["url"], headers=HEADERS, timeout=30)
        if response.status_code != 200:
            print(f"⚠️ {league_name}: HTTP {response.status_code}")
            return pd.DataFrame()

        data = response.json().get("response", [])
        if not data:
            print(f"⚠️ {league_name}: No data returned.")
            return pd.DataFrame()

        teams = []
        for t in data:
            team = t.get("team", {})
            venue = t.get("venue", {})
            teams.append({
                "sport": league_name,
                "team": team.get("name"),
                "city": team.get("city"),
                "abbreviation": team.get("code"),
                "stadium": venue.get("name"),
                "capacity": venue.get("capacity"),
                "surface": venue.get("surface"),
                "updated_at": pd.Timestamp.utcnow()
            })

        df = pd.DataFrame(teams)
        out_path = DATA_DIR / f"{league_name.lower()}_team_stats.csv"
        df.to_csv(out_path, index=False)
        print(f"✅ Saved {league_name} stats → {out_path} ({len(df)} teams)")
        return df

    except Exception as e:
        print(f"❌ {league_name} fetch failed: {e}")
        return pd.DataFrame()


def main():
    all_data = []
    for league, cfg in SPORTS.items():
        df = fetch_league(league, cfg)
        if not df.empty:
            all_data.append(df)

    if not all_data:
        print("⚠️ No leagues returned data.")
        return

    combined = pd.concat(all_data, ignore_index=True)
    combined.to_csv(OUT_FILE, index=False)
    print(f"🏁 Unified file saved → {OUT_FILE} ({len(combined)} rows)")


if __name__ == "__main__":
    main()
