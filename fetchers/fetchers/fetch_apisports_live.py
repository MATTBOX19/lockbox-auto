#!/usr/bin/env python3
import os
import requests
import pandas as pd
from datetime import datetime
import time

API_KEY = os.getenv("APISPORTS_KEY")
if not API_KEY:
    raise EnvironmentError("Missing $APISPORTS_KEY environment variable.")

HEADERS = {"x-apisports-key": API_KEY}
DATA_DIR = "Data"
os.makedirs(DATA_DIR, exist_ok=True)

# league name → (sport type, league id)
LEAGUES = {
    "NFL": ("american-football", 1),
    "NCAAF": ("american-football", 2),
    "NBA": ("basketball", 12),
    "MLB": ("baseball", 1),
    "NHL": ("hockey", 57),
}


# ---------------------- HELPERS ----------------------

def fetch_json(url, params=None):
    """Simple JSON fetch wrapper."""
    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=20)
        r.raise_for_status()
        data = r.json()
        if not data.get("response"):
            print(f"⚠️ Empty response from {url}")
        return data
    except Exception as e:
        print(f"❌ Error fetching {url}: {e}")
        return {}


# ---------------------- FOOTBALL ----------------------

def fetch_standings(league_name, league_id, season=2025):
    """Fetch NFL/NCAAF standings (wins/losses/points)."""
    url = "https://v1.american-football.api-sports.io/standings"
    data = fetch_json(url, {"league": league_id, "season": season})

    if not data.get("response"):
        print(f"⚠️ {league_name}: no standings data.")
        return pd.DataFrame()

    rows = []
    for t in data["response"]:
        team = t.get("team", {}).get("name")
        if not team:
            continue
        points = t.get("points", {})
        rows.append({
            "league": league_name,
            "team": team,
            "wins": t.get("won"),
            "losses": t.get("lost"),
            "ties": t.get("ties"),
            "points_for": points.get("for"),
            "points_against": points.get("against"),
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        df["games_played"] = df[["wins", "losses", "ties"]].fillna(0).sum(axis=1)
        df["win_pct"] = (df["wins"] / df["games_played"]).round(3)
        print(f"✅ {league_name}: {len(df)} teams fetched from standings.")
    return df


# ---------------------- GENERIC TEAMS ----------------------

def fetch_teams(sport, league_id, season=2025):
    """Fetch metadata for non-football leagues."""
    url = f"https://v1.{sport}.api-sports.io/teams"
    data = fetch_json(url, {"league": league_id, "season": season})
    if not data.get("response"):
        print(f"⚠️ {sport.upper()} {season}: no team data.")
        return pd.DataFrame()
    df = pd.json_normalize(data["response"])
    print(f"✅ {sport.upper()} {season}: {len(df)} teams.")
    return df


# ---------------------- MAIN ----------------------

def main():
    print(f"🏁 Starting API-Sports fetcher at {datetime.now():%Y-%m-%d %H:%M:%S}")
    all_dfs = []

    for league, (sport, league_id) in LEAGUES.items():
        print(f"🏈 Fetching league: {league} ({sport})")

        if sport == "american-football":
            df = fetch_standings(league, league_id)
        else:
            df = fetch_teams(sport, league_id)

        if df is None or df.empty:
            print(f"⚠️ {league}: no data returned.")
            continue

        out_path = os.path.join(DATA_DIR, f"{league.lower()}_stats.csv")
        df.to_csv(out_path, index=False)
        all_dfs.append(df)
        print(f"💾 Saved {league} → {out_path}")

        time.sleep(0.5)  # rate limit

    if not all_dfs:
        print("⚠️ No leagues returned any data.")
        return

    combined = pd.concat(all_dfs, ignore_index=True)
    combined_path = os.path.join(DATA_DIR, "team_stats_latest.csv")
    combined.to_csv(combined_path, index=False)
    print(f"\n🎉 Combined {len(combined)} total rows across {len(all_dfs)} leagues.")
    print(f"✅ Saved merged file → {combined_path}")
    print(f"🕒 Completed at {datetime.now():%Y-%m-%d %H:%M:%S}")


if __name__ == "__main__":
    main()
