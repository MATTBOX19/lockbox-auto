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
  Data/<sport>_team_stats.csv   ← new per-sport files (kept and combined)
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
        "endpoint": "https://api.sportsdata.io/v3/nfl/stats/json/TeamGameStatsFinal/{season}/{week}",
        "season": "2025",
        "weeks": list(range(1, 19)),
    },
    "NCAAF": {
        "endpoint": "https://api.sportsdata.io/v3/cfb/stats/json/TeamGameStatsByWeek/{season}/{week}",
        "season": "2025REG",
        "weeks": list(range(1, 15)),
    },
    "NBA": {
        "endpoint": "https://api.sportsdata.io/v3/nba/stats/json/TeamGameStatsByDate/{date}",
        "days": 120,
    },
    "NHL": {
        "endpoint": "https://api.sportsdata.io/v3/nhl/stats/json/TeamGameStatsByDate/{date}",
        "days": 120,
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

            # ✅ Add both home and away team perspectives
            games.append({
                "Date": date,
                "Sport": sport,
                "Team": home,
                "Opponent": away,
                "Score": home_score,
                "OppScore": away_score,
                "Yards": g.get("OffensiveYards"),
                "OppYards": g.get("OpponentOffensiveYards"),
                "Turnovers": g.get("Turnovers"),
                "OppTurnovers": g.get("OpponentTurnovers"),
                "Possession": g.get("TimeOfPossessionMinutes"),
            })
            games.append({
                "Date": date,
                "Sport": sport,
                "Team": away,
                "Opponent": home,
                "Score": away_score,
                "OppScore": home_score,
                "Yards": g.get("OpponentOffensiveYards"),
                "OppYards": g.get("OffensiveYards"),
                "Turnovers": g.get("OpponentTurnovers"),
                "OppTurnovers": g.get("Turnovers"),
                "Possession": g.get("OpponentTimeOfPossessionMinutes"),
            })
        except Exception as e:
            print(f"⚠️ Skipping {sport} game parse error: {e}")
    return games


def fetch_all():
    combined = []

    for sport, cfg in SPORTS_CONFIG.items():
        print(f"📊 Fetching {sport}...")
        sport_games = []

        if "weeks" in cfg:
            for w in cfg["weeks"]:
                url = cfg["endpoint"].format(season=cfg["season"], week=w)
                data = safe_get(url)
                parsed = parse_games(sport, data)
                if parsed:
                    sport_games.extend(parsed)
                print(f"✅ {sport} week {w}: {len(parsed)} games")

        elif "days" in cfg:
            for i in range(cfg["days"]):
                day = (datetime.utcnow() - timedelta(days=i)).strftime("%Y-%m-%d")
                url = cfg["endpoint"].format(date=day)
                data = safe_get(url)
                parsed = parse_games(sport, data)
                if parsed:
                    sport_games.extend(parsed)
                print(f"✅ {sport} {day}: {len(parsed)} games")

        if sport_games:
            df_sport = pd.DataFrame(sport_games).drop_duplicates()
            df_sport.to_csv(DATA_DIR / f"{sport.lower()}_team_stats.csv", index=False)
            print(f"💾 Saved {sport} stats → Data/{sport.lower()}_team_stats.csv ({len(df_sport)} rows)")
            combined.extend(sport_games)

    if not combined:
        print("⚠️ No games fetched across all sports.")
        return

    df_all = pd.DataFrame(combined).drop_duplicates()
    df_all.sort_values(["Date", "Sport"], inplace=True)
    df_all.to_csv(OUT_FILE, index=False)
    print(f"🏁 Saved unified file → {OUT_FILE} ({len(df_all)} total rows)")


if __name__ == "__main__":
    fetch_all()
