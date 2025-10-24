#!/usr/bin/env python3
"""
fetch_sportsdata.py — unified SportsData.io team stats fetcher for LockBox

Purpose:
  • Fetches final team-level game stats for all major sports (NFL, NCAAF, NBA, NHL, MLB)
  • Normalizes them into one consistent CSV → Data/team_stats_latest.csv
  • Pulls only *completed* games so results are stable for training/learning

Environment:
  SPORTSDATA_IO = your API key (b72cb4a769884f22b82157d6ba2da26b)

Output:
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

# --- Configurations per sport ---
SPORTS_CONFIG = {
    "NFL": {
        "endpoint": "https://api.sportsdata.io/v4/nfl/stats/json/TeamGameStatsByWeek/2025REG/{week}",
        "weeks": [8],  # we can make this dynamic later
    },
    "NCAAF": {
        "endpoint": "https://api.sportsdata.io/v4/cfb/stats/json/TeamGameStatsByWeek/2025REG/{week}",
        "weeks": [8],
    },
    "NBA": {
        "endpoint": "https://api.sportsdata.io/v4/nba/stats/json/TeamGameStatsByDate/{date}",
        "days": 7,
    },
    "NHL": {
        "endpoint": "https://api.sportsdata.io/v4/nhl/stats/json/TeamGameStatsByDate/{date}",
        "days": 7,
    },
    "MLB": {
        "endpoint": "https://api.sportsdata.io/v4/mlb/stats/json/TeamGameStatsByDate/{date}",
        "days": 7,
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
            date = g.get("Day", g.get("DayKey", g.get("GameDate"))) or g.get("Date")
            if not date:
                continue
            if isinstance(date, str) and "T" in date:
                date = date.split("T")[0]

            # figure out home vs away
            if "HomeTeam" in g and "AwayTeam" in g:
                home = g["HomeTeam"]
                away = g["AwayTeam"]
            elif "Team" in g and "Opponent" in g:
                home = g["Team"]
                away = g["Opponent"]
            else:
                continue

            home_score = g.get("HomeScore", g.get("Score", 0))
            away_score = g.get("AwayScore", g.get("OpponentScore", 0))
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
                "HomeYards": g.get("OffensiveYards", None),
                "AwayYards": g.get("OpponentOffensiveYards", None),
                "HomeTurnovers": g.get("Turnovers", None),
                "AwayTurnovers": g.get("OpponentTurnovers", None),
                "HomePossession": g.get("TimeOfPossessionMinutes", None),
                "AwayPossession": g.get("OpponentTimeOfPossessionMinutes", None),
            })
        except Exception as e:
            print(f"⚠️ Skipping game due to parse error: {e}")
    return games


def fetch_all():
    all_games = []

    for sport, cfg in SPORTS_CONFIG.items():
        print(f"📊 Fetching {sport}...")

        if "weeks" in cfg:
            for w in cfg["weeks"]:
                url = cfg["endpoint"].format(week=w)
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
