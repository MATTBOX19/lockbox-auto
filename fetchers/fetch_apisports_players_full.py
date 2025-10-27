#!/usr/bin/env python3
"""
fetch_apisports_players_full.py
Fetches full player statistics for all LockBox sports using API-SPORTS.

Leagues covered:
  - NFL (american-football)
  - NCAAF (american-football)
  - NBA (basketball)
  - MLB (baseball)
  - NHL (hockey)

Creates per-league and combined player stats CSVs under /Data.
"""

import os
import time
import requests
import pandas as pd
from datetime import datetime
from pathlib import Path

API_KEY = os.getenv("APISPORTS_KEY")
if not API_KEY:
    raise EnvironmentError("Missing $APISPORTS_KEY environment variable.")

HEADERS = {"x-apisports-key": API_KEY}

DATA_DIR = Path("Data")
DATA_DIR.mkdir(exist_ok=True)

LEAGUES = {
    "nfl": ("american-football", 1),
    "ncaaf": ("american-football", 2),
    "nba": ("basketball", 12),
    "mlb": ("baseball", 1),
    "nhl": ("hockey", 57),
}

def fetch_team_list(league_name: str) -> pd.DataFrame:
    """Load team list from existing CSV (e.g., Data/nfl_team_stats.csv)."""
    path = Path(__file__).resolve().parent.parent / "Data" / f"{league_name}_team_stats.csv"
    if not path.exists():
        print(f"⚠️ Missing team file: {path}")
        return pd.DataFrame()
    try:
        df = pd.read_csv(path)
        if "id" not in df.columns:
            print(f"⚠️ Team file {path} missing 'id' column.")
            return pd.DataFrame()
        return df
    except Exception as e:
        print(f"❌ Failed to read {path}: {e}")
        return pd.DataFrame()

def fetch_player_stats(sport: str, league_id: int, team_id: int, season: int = 2025) -> list:
    """Fetch player stats for one team."""
    url = f"https://v1.{sport}.api-sports.io/players/statistics"
    params = {"league": league_id, "season": season, "team": team_id}
    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=25)
        data = r.json()
        if not data.get("response"):
            return []
        players = []
        for p in data["response"]:
            base = {
                "player_id": p.get("player", {}).get("id"),
                "name": p.get("player", {}).get("name"),
                "age": p.get("player", {}).get("age"),
                "position": p.get("player", {}).get("position"),
                "team_id": team_id,
                "sport": sport,
                "league_id": league_id,
            }
            stats = p.get("statistics", [{}])[0]
            # Generic fields common across sports
            base.update({
                "games_played": stats.get("games", {}).get("appearences"),
                "points": stats.get("points", {}).get("for", {}).get("total")
                if isinstance(stats.get("points", {}).get("for"), dict)
                else stats.get("points"),
                "yards": stats.get("yards") or None,
                "touchdowns": stats.get("touchdowns", {}).get("total")
                if isinstance(stats.get("touchdowns"), dict)
                else stats.get("touchdowns"),
                "assists": stats.get("assists") or None,
                "rebounds": stats.get("rebounds") or None,
                "shots": stats.get("shots") or None,
                "minutes": stats.get("games", {}).get("minutes"),
            })
            players.append(base)
        return players
    except Exception as e:
        print(f"❌ {sport.upper()} fetch failed for team {team_id}: {e}")
        return []

def process_league(league_name: str, sport: str, league_id: int):
    """Fetch all player stats for a league."""
    teams_df = fetch_team_list(league_name)
    if teams_df.empty:
        print(f"⚠️ No teams returned for {league_name.upper()}")
        return pd.DataFrame()

    all_players = []
    for _, row in teams_df.iterrows():
        team_id = row["id"]
        team_name = row.get("team") or "Unknown"
        print(f"📊 Fetching {sport.upper()} player stats for {team_name} (id={team_id})...")
        players = fetch_player_stats(sport, league_id, team_id)
        if players:
            all_players.extend(players)
            print(f"✅ Got {len(players)} players for {team_name}")
        else:
            print(f"⚠️ No stats for {team_name}")
        time.sleep(1.5)  # rate limit

    if not all_players:
        print(f"⚠️ No player data fetched for {league_name.upper()}")
        return pd.DataFrame()

    df = pd.DataFrame(all_players)
    out_file = DATA_DIR / f"{league_name}_player_stats_2025.csv"
    df.to_csv(out_file, index=False)
    print(f"✅ Saved {len(df)} players to {out_file}")
    return df

def main():
    combined = []
    for league, (sport, league_id) in LEAGUES.items():
        print(f"\n🏈 Processing league: {league.upper()} ({sport}, id={league_id})")
        df = process_league(league, sport, league_id)
        if not df.empty:
            combined.append(df)

    if combined:
        all_players = pd.concat(combined, ignore_index=True)
        all_path = DATA_DIR / "player_stats_all_latest.csv"
        all_players.to_csv(all_path, index=False)
        print(f"\n🎉 Combined {len(all_players)} player stats saved to {all_path}")
    else:
        print("⚠️ No player data fetched from any league.")

    print(f"🕒 Completed at {datetime.utcnow().isoformat()} UTC")

if __name__ == "__main__":
    main()
