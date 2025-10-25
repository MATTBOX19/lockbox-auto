#!/usr/bin/env python3
"""
fetch_sportsdata.py — LockBox SportsData.io Team Stats Aggregator (offline-safe)

Purpose:
  • Fetch team stats for NFL, NCAAF, NBA, NHL, MLB
  • Auto-rebuild per-sport CSVs from team_stats_latest.csv if quota is exceeded
  • Never overwrites good data when API is blocked

Environment:
  SPORTSDATA_IO = your SportsData.io API key
"""

import os
import time
import random
import requests
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path

API_KEY = os.getenv("SPORTSDATA_IO")
if not API_KEY:
    print("⚠️ Missing SPORTSDATA_IO key (offline rebuild mode only).")

DATA_DIR = Path("Data")
DATA_DIR.mkdir(exist_ok=True)
OUT_FILE = DATA_DIR / "team_stats_latest.csv"

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
        "days": 30,
    },
    "NHL": {
        "endpoint": "https://api.sportsdata.io/v3/nhl/stats/json/TeamGameStatsByDate/{date}",
        "days": 30,
    },
    "MLB": {
        "endpoint": "https://api.sportsdata.io/v3/mlb/stats/json/TeamGameStatsByDate/{date}",
        "days": 30,
    },
}


def safe_get(url):
    try:
        r = requests.get(url, headers={"Ocp-Apim-Subscription-Key": API_KEY}, timeout=20)
        if r.status_code == 403 and "quota" in r.text.lower():
            print("🚫 Quota exceeded — switching to offline rebuild mode.")
            raise StopIteration
        if r.status_code != 200:
            print(f"⚠️ {url} → HTTP {r.status_code}")
            return []
        return r.json()
    except StopIteration:
        raise
    except Exception as e:
        print(f"❌ Error fetching {url}: {e}")
        return []


def parse_games(sport, data):
    games = []
    for g in data or []:
        try:
            date = g.get("Day") or g.get("DayKey") or g.get("GameDate") or g.get("Date")
            if isinstance(date, str) and "T" in date:
                date = date.split("T")[0]
            home = g.get("HomeTeam") or g.get("Team")
            away = g.get("AwayTeam") or g.get("Opponent")
            if not home or not away:
                continue
            home_score = g.get("HomeScore") or g.get("Score") or 0
            away_score = g.get("AwayScore") or g.get("OpponentScore") or 0
            games.append({
                "Date": date,
                "Sport": sport,
                "Home": home,
                "Away": away,
                "HomeScore": home_score,
                "AwayScore": away_score,
                "Winner": home if float(home_score) > float(away_score) else away,
            })
        except Exception as e:
            print(f"⚠️ {sport} parse error: {e}")
    return games


def append_or_keep(path, new_rows):
    if not new_rows:
        print(f"↩️ No new data for {path} (keeping existing).")
        return
    df_new = pd.DataFrame(new_rows)
    if path.exists():
        try:
            df_old = pd.read_csv(path)
            df = pd.concat([df_old, df_new], ignore_index=True).drop_duplicates()
        except Exception:
            df = df_new
    else:
        df = df_new
    df.to_csv(path, index=False)
    print(f"💾 Saved {path} ({len(df)} rows).")


def rebuild_from_latest():
    """If we’re offline or quota-limited, rebuild per-sport CSVs from team_stats_latest.csv."""
    if not OUT_FILE.exists():
        print("⚠️ No unified file found to rebuild from.")
        return False

    df = pd.read_csv(OUT_FILE)
    if "Sport" not in df.columns:
        print("⚠️ Unified file has no 'Sport' column — skipping rebuild.")
        return False

    for sport in df["Sport"].dropna().unique():
        sport_df = df[df["Sport"] == sport]
        path = DATA_DIR / f"{sport.lower()}_team_stats.csv"
        sport_df.to_csv(path, index=False)
        print(f"🔁 Restored {sport} → {path} ({len(sport_df)} rows)")
    return True


def fetch_all():
    combined = []

    try:
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
                    time.sleep(0.5 + random.random() * 0.5)

            elif "days" in cfg:
                for i in range(cfg["days"]):
                    day = (datetime.utcnow() - timedelta(days=i)).strftime("%Y-%m-%d")
                    url = cfg["endpoint"].format(date=day)
                    data = safe_get(url)
                    parsed = parse_games(sport, data)
                    if parsed:
                        sport_games.extend(parsed)
                    print(f"✅ {sport} {day}: {len(parsed)} games")
                    time.sleep(0.5 + random.random() * 0.5)

            if sport_games:
                csv_path = DATA_DIR / f"{sport.lower()}_team_stats.csv"
                append_or_keep(csv_path, sport_games)
                combined.extend(sport_games)

    except StopIteration:
        print("🛑 Quota stop detected — performing offline rebuild.")
        rebuild_from_latest()

    # Merge available data
    parts = list(DATA_DIR.glob("*_team_stats.csv"))
    if not parts:
        print("⚠️ No per-sport CSVs to merge.")
        return

    dfs = []
    for p in parts:
        try:
            dfs.append(pd.read_csv(p))
        except Exception as e:
            print(f"⚠️ Skipping {p}: {e}")

    if not dfs:
        print("⚠️ Nothing to merge.")
        return

    df_all = pd.concat(dfs, ignore_index=True).drop_duplicates()
    df_all.sort_values(["Date", "Sport"], inplace=True, ignore_index=True)
    df_all.to_csv(OUT_FILE, index=False)
    print(f"🏁 Unified stats written → {OUT_FILE} ({len(df_all)} rows).")


if __name__ == "__main__":
    fetch_all()
