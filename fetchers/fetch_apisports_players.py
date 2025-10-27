#!/usr/bin/env python3
"""
fetch_apisports_players.py — LockBox player stats fetcher
Pulls player-level statistics from API-Sports (NFL first, extendable to other leagues).
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

# for now: start with NFL → later extend to other sports
SPORT = "american-football"
LEAGUE_ID = 1
SEASON = 2025


def fetch_players(league_id: int, season: int) -> pd.DataFrame:
    """Fetch player statistics by team for the league."""
    all_players = []
    url = f"https://v1.{SPORT}.api-sports.io/players/statistics"
    print(f"📊 Fetching {SPORT.upper()} player stats for league={league_id} season={season}...")

    # pull team list first
    teams_url = f"https://v1.{SPORT}.api-sports.io/teams"
    teams_resp = requests.get(teams_url, headers=HEADERS, params={"league": league_id, "season": season}, timeout=30)
    teams = teams_resp.json().get("response", [])
    if not teams:
        print("⚠️ No teams found — check league/season.")
        return pd.DataFrame()

    for t in teams:
        team_id = t.get("id")
        team_name = t.get("name")
        if not team_id:
            continue

        params = {"league": league_id, "season": season, "team": team_id}
        try:
            r = requests.get(url, headers=HEADERS, params=params, timeout=30)
            data = r.json()
        except Exception as e:
            print(f"❌ Failed for team {team_name}: {e}")
            continue

        players = data.get("response", [])
        for p in players:
            player = p.get("player", {})
            stats = p.get("statistics", [{}])[0]
            entry = {
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

    if not all_players:
        print("⚠️ No player stats returned.")
        return pd.DataFrame()

    df = pd.DataFrame(all_players)
    df.to_csv(OUT_FILE, index=False)
    print(f"✅ Saved {len(df)} player rows → {OUT_FILE}")
    return df


def main():
    df = fetch_players(LEAGUE_ID, SEASON)
    if not df.empty:
        print(df.head())


if __name__ == "__main__":
    main()
