#!/usr/bin/env python3
"""
fetch_sportsdata.py — LockBox SportsData.io Team Stats Aggregator

Purpose:
  • Fetch final team game stats for NFL, NCAAF, NBA, NHL, and MLB.
  • Works with v3 API (free or trial tier).
  • Saves unified stats to Data/team_stats_latest.csv for model learning.

Environment:
  SPORTSDATA_IO = your SportsData.io API key

Outputs:
  Data/team_stats_latest.csv
"""

import os
import requests
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path

API_KEY = os.getenv("SPORTSDATA_IO")
if not API_KEY:
    raise SystemExit("❌ Missing SPORTSDATA_IO environment variable")

DATA_DIR = Path("Data")
DATA_DIR.mkdir(exist_ok=True)
OUT_FILE = DATA_DIR / "team_stats_latest.csv"

# --- Sports Config (v3 endpoints) ---
SPORTS_CONFIG = {
    "NFL": {
        "endpoint": "https://api.sportsdata.io/v3/nfl/stats/json/TeamGameStatsByWeek/{season}/{week}",
        "season": "2024REG",
        "weeks": [1, 2, 3, 4, 5, 6, 7, 8]  # you can adjust this to backfill more
    },
    "NCAAF": {
        "endpoint": "https://api.sportsdata.io/v3/cfb/stats/json/TeamGameStatsByWeek/{season}/{week}",
        "season": "2024REG",
        "weeks": [1, 2, 3, 4, 5, 6, 7, 8],
    },
    "NBA": {
        "endpoint": "https://api.sportsdata.io/v3/nba/stats/json/TeamGameStatsByDate/{date}",
        "days": 24,
    },
    "NHL": {
        "endpoint": "https://api.sportsdata.io/v3/nhl/stats/json/TeamGameStatsByDate/{date}",
        "days": 34,
    },
    "MLB": {
        "endpoint": "https://api.sportsdata.io/v3/mlb/stats/json/TeamGameStatsByDate/{date}",
        "days": 240,
    },
}


def safe_get(url):
    try:
        r = requests.get(url, headers={"Ocp-Apim-Subscription-Key": API_KEY}, timeout=30)
        if r.status_code != 200:
            print(f"⚠️ {url} → HTTP {r.status_code}")
            return []
        return r.json()
    except Exception as e:
        print(f"❌ Error fetching {url}: {e}")
        return []


def parse_games(sport, data):
    games = []
    for g in data:
        try:
            date = g.get("Day") or g.get("DayKey") or g.get("GameDate") or g.get("Date")
            if not date:
                continue
            if isinstance(date, str) and "T" in date:
                date = date.split("T")[0]

            home = g.get("HomeTeam") or g.get("Team")
            away = g.get("AwayTeam") or g.get("Opponent")
            if not home or not away:
                continue

            home_score = g.get("HomeScore") or g.get("Score") or 0
            away_score = g.get("AwayScore") or g.get("OpponentScore") or 0
            if home_score is None or away_score is None:
                continue

            winner = home if float(home_score) > float(away_score) else away

            games.append({
                "Date": date,
                "Sport": sport,
                "Home": home,
                "Away": away,
                "HomeScore": home_score,
                "AwayScore": away_score,
                "Winner": winner,
                "HomeYards": g.get("OffensiveYards"),
                "AwayYards": g.get("OpponentOffensiveYards"),
                "HomeTurnovers": g.get("Turnovers"),
                "AwayTurnovers": g.get("OpponentTurnovers"),
                "HomePossession": g.get("TimeOfPossessionMinutes"),
                "AwayPossession": g.get("OpponentTimeOfPossessionMinutes"),
            })
        except Exception as e:
            print(f"⚠️ Skipping {sport} game parse error: {e}")
    return games


def fetch_all():
    all_games = []

    for sport, cfg in SPORTS_CONFIG.items():
        print(f"📊 Fetching {sport}...")

        if "weeks" in cfg:
            for w in cfg["weeks"]:
                url = cfg["endpoint"].format(season=cfg["season"], week=w)
                data = safe_get(url)
                parsed = parse_games(sport, data)
                print(f"✅ {sport} week {w}: {len(parsed)} games")
                all_games.extend(parsed)

        elif "days" in cfg:
            for i in range(cfg["days"]):
                day = (datetime.utcnow() - timedelta(days=i)).strftime("%Y-%m-%d")
                url = cfg["endpoint"].format(date=day)
                data = safe_get(url)
                parsed = parse_games(sport, data)
                print(f"✅ {sport} {day}: {len(parsed)} games")
                all_games.extend(parsed)

    if not all_games:
        print("⚠️ No games fetched.")
        return

    df = pd.DataFrame(all_games)
    df.drop_duplicates(inplace=True)
    df.sort_values(["Date", "Sport"], inplace=True)

    df.to_csv(OUT_FILE, index=False)
    print(f"🏁 Saved → {OUT_FILE} ({len(df)} rows)")


if __name__ == "__main__":
    fetch_all()
