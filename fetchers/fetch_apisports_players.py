#!/usr/bin/env python3
"""
fetch_apisports_players.py — LockBox player stats fetcher (NFL only)
Falls back to last active season if current season is empty.
Outputs: Data/player_stats_latest.csv
"""

import os
import time
import pandas as pd
import requests
from datetime import datetime
from pathlib import Path

API_KEY = os.getenv("APISPORTS_KEY")
if not API_KEY:
    raise EnvironmentError("Missing $APISPORTS_KEY environment variable.")

HEADERS = {"x-apisports-key": API_KEY}

DATA_DIR = Path("Data")
DATA_DIR.mkdir(exist_ok=True)
OUT_FILE = DATA_DIR / "player_stats_latest.csv"

SPORT = "american-football"
LEAGUE_ID = 1
SEASONS = [2025, 2024, 2023]  # will auto-fallback

def fetch_players(league_id: int, season: int) -> pd.DataFrame:
    """Fetch player statistics by team for the league."""
    all_players = []
    url = f"https://v1.{SPORT}.api-sports.io/players/statistics"
    print(f"📊 Fetching {SPORT.upper()} player stats for league={league_id} season={season}...")

    # fetch teams
    teams_url = f"https://v1.{SPORT}.api-sports.io/teams"
    teams_resp = requests.get(teams_url, headers=HEADERS, params={"league": league_id, "season": season}, timeout=30)
    teams = teams_resp.json().get("response", [])
    if not teams:
        print(f"⚠️ No teams for {season}")
        return pd.DataFrame()

    for t in teams:
        team_id = t.get("id")
        team_name = t.get("name")
        if not team_id:
            continue
        try:
            r = requests.get(url, headers=HEADERS, params={"league": league_id, "season": season, "team": team_id}, timeout=30)
            data = r.json()
        except Exception as e:
            print(f"❌ Failed for team {team_name}: {e}")
            continue

        players = data.get("response", [])
        for p in players:
            player = p.get("player", {})
            stats = p.get("statistics", [{}])[0]
            entry = {
                "season": season,
                "team": team_name,
                "player_id": player.get("id"),
                "player_name": player.get("name"),
                "position": player.get("position"),
                "games_played": stats.get("games", {}).get("appearences"),
                "yards": stats.get("passes", {}).get("yards") or stats.get("rushing", {}).get("yards"),
                "touchdowns": stats.get("passes", {}).get("touchdowns") or stats.get("rushing", {}).get("touchdowns"),
                "interceptions": stats.get("passes", {}).get("interceptions"),
                "fumbles": stats.get("fumbles", {}).get("total"),
                "updated_at": datetime.utcnow().isoformat()
            }
            all_players.append(entry)
        time.sleep(0.4)

    return pd.DataFrame(all_players)

def main():
    for season in SEASONS:
        df = fetch_players(LEAGUE_ID, season)
        if not df.empty:
            df.to_csv(OUT_FILE, index=False)
            print(f"✅ Saved {len(df)} player rows for season={season} → {OUT_FILE}")
            print(f"🕒 Completed at {datetime.utcnow().isoformat()} UTC")
            return
    print("⚠️ No player data found in available seasons.")

if __name__ == "__main__":
    main()
