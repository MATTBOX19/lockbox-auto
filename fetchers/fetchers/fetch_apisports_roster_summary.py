#!/usr/bin/env python3
"""
fetch_apisports_roster_summary.py — LockBox AI Player Roster + Injury Summary
Builds team-level summary stats (roster depth, experience, injuries) for all sports.

Output: Data/player_team_summary.csv
"""

import os
import time
import requests
import pandas as pd
from datetime import datetime
from pathlib import Path

API_KEY = os.getenv("APISPORTS_KEY")
if not API_KEY:
    raise EnvironmentError("Missing $APISPORTS_KEY environment variable")

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


def fetch_teams(sport: str, league_id: int, season=2025) -> list:
    """Fetch all team IDs for a given league."""
    url = f"https://v1.{sport}.api-sports.io/teams"
    params = {"league": league_id, "season": season}
    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=15)
        js = r.json()
        return [t.get("id") or t.get("team", {}).get("id") for t in js.get("response", [])]
    except Exception as e:
        print(f"❌ {sport.upper()} teams fetch failed: {e}")
        return []


def fetch_players_for_team(sport: str, team_id: int, season=2025) -> pd.DataFrame:
    """Fetch roster for a team."""
    url = f"https://v1.{sport}.api-sports.io/players"
    params = {"team": team_id, "season": season}
    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=20)
        js = r.json()
        players = js.get("response", [])
        if not players:
            return pd.DataFrame()
        df = pd.json_normalize(players)
        df["team_id"] = team_id
        return df
    except Exception as e:
        print(f"⚠️ {sport.upper()} team={team_id}: roster fetch failed ({e})")
        return pd.DataFrame()


def fetch_injuries(sport: str, league_id: int, season=2025) -> pd.DataFrame:
    """Fetch active injury reports."""
    url = f"https://v1.{sport}.api-sports.io/injuries"
    params = {"league": league_id, "season": season}
    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=20)
        js = r.json()
        inj = js.get("response", [])
        if not inj:
            return pd.DataFrame()
        df = pd.json_normalize(inj)
        df["league_id"] = league_id
        return df
    except Exception as e:
        print(f"⚠️ {sport.upper()} injuries fetch failed ({e})")
        return pd.DataFrame()


def summarize_team(df_players: pd.DataFrame, df_inj: pd.DataFrame) -> pd.DataFrame:
    """Aggregate per-team stats."""
    if df_players.empty:
        return pd.DataFrame()

    # Basic player stats
    summary = (
        df_players.groupby("team_id")
        .agg(
            total_players=("player.id", "count"),
            avg_age=("player.age", "mean"),
            avg_exp=("player.experience", "mean"),
        )
        .reset_index()
    )

    # Add injury counts
    if not df_inj.empty and "player.id" in df_inj:
        inj_count = df_inj.groupby("team.id")["player.id"].count().reset_index()
        inj_count.rename(columns={"team.id": "team_id", "player.id": "injured_players"}, inplace=True)
        summary = summary.merge(inj_count, on="team_id", how="left")
        summary["injured_players"].fillna(0, inplace=True)
    else:
        summary["injured_players"] = 0

    # Derived roster health metrics
    summary["injury_pct"] = (summary["injured_players"] / summary["total_players"]).round(3)
    summary["roster_health"] = (1 - summary["injury_pct"]).round(3)
    return summary


def main():
    all_data = []
    for league, (sport, league_id) in LEAGUES.items():
        print(f"\n🏈 Processing {league.upper()} ({sport}, id={league_id})")
        team_ids = fetch_teams(sport, league_id)
        if not team_ids:
            print(f"⚠️ No teams returned for {league.upper()}")
            continue

        inj_df = fetch_injuries(sport, league_id)
        all_players = []
        for tid in team_ids:
            df_team = fetch_players_for_team(sport, tid)
            if not df_team.empty:
                all_players.append(df_team)
            time.sleep(0.4)

        if not all_players:
            print(f"⚠️ {league.upper()}: no player data.")
            continue

        df_players = pd.concat(all_players, ignore_index=True)
        df_summary = summarize_team(df_players, inj_df)
        df_summary["league"] = league.upper()
        all_data.append(df_summary)
        print(f"✅ {league.upper()}: summarized {len(df_summary)} teams")

    if not all_data:
        print("⚠️ No player data fetched from any league.")
        return

    combined = pd.concat(all_data, ignore_index=True)
    out_path = DATA_DIR / "player_team_summary.csv"
    combined.to_csv(out_path, index=False)
    print(f"🎉 Saved {len(combined)} team summaries → {out_path}")
    print(f"🕒 Completed at {datetime.utcnow().isoformat()} UTC")


if __name__ == "__main__":
    main()
