import os
import requests
import pandas as pd
from datetime import datetime

API_KEY = os.getenv("APISPORTS_KEY")
if not API_KEY:
    raise EnvironmentError("Missing $APISPORTS_KEY environment variable.")
HEADERS = {"x-apisports-key": API_KEY}

DATA_DIR = "Data"
os.makedirs(DATA_DIR, exist_ok=True)

LEAGUES = {
    "NFL": ("american-football", 1),
    "NCAAF": ("american-football", 2),
    "NBA": ("basketball", 12),
    "MLB": ("baseball", 1),
    "NHL": ("hockey", 57),
}

def fetch_json(url, params=None):
    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
        return data
    except Exception as e:
        print(f"❌ Request failed: {e}")
        return {}

def fetch_standings(league_name, league_id, season):
    """Fetch football standings."""
    url = "https://v1.american-football.api-sports.io/standings"
    print(f"🏈 Calling standings API → {url}?league={league_id}&season={season}")
    data = fetch_json(url, {"league": league_id, "season": season})
    if not data.get("response"):
        print(f"⚠️ {league_name}: no standings returned.")
        return pd.DataFrame()

    rows = []
    for item in data["response"]:
        team = item.get("team", {}).get("name")
        if not team:
            continue
        pts = item.get("points", {})
        rows.append({
            "league": league_name,
            "team": team,
            "wins": item.get("won"),
            "losses": item.get("lost"),
            "ties": item.get("ties"),
            "points_for": pts.get("for"),
            "points_against": pts.get("against"),
            "streak": item.get("streak"),
        })
    df = pd.DataFrame(rows)
    print(f"✅ {league_name}: {len(df)} records from standings API")
    return df

def fetch_teams(sport, league_id, season):
    """Generic teams fetch for other sports."""
    url = f"https://v1.{sport}.api-sports.io/teams"
    print(f"🏀 Fetching teams from {url}?league={league_id}&season={season}")
    data = fetch_json(url, {"league": league_id, "season": season})
    if not data.get("response"):
        print(f"⚠️ {sport.upper()} returned no teams for {season}.")
        return pd.DataFrame()
    df = pd.json_normalize(data["response"])
    print(f"✅ {sport.upper()}: {len(df)} teams retrieved.")
    return df

def main():
    print(f"🚀 Starting API-Sports data fetcher at {datetime.now():%Y-%m-%d %H:%M:%S}\n")

    all_dfs = []
    for league, (sport, league_id) in LEAGUES.items():
        print(f"🔹 Fetching {league} ({sport})...")

        if sport == "american-football":
            df = fetch_standings(league, league_id, 2025)
        else:
            df = fetch_teams(sport, league_id, 2025)

        if df.empty:
            print(f"⚠️ {league}: no data fetched.\n")
            continue

        out_path = os.path.join(DATA_DIR, f"{league.lower()}_stats.csv")
        df.to_csv(out_path, index=False)
        print(f"💾 Saved {league} → {out_path}\n")
        all_dfs.append(df)

    if all_dfs:
        combined = pd.concat(all_dfs, ignore_index=True)
        combined_path = os.path.join(DATA_DIR, "team_stats_latest.csv")
        combined.to_csv(combined_path, index=False)
        print(f"🎉 Combined {len(combined)} rows across {len(all_dfs)} leagues.")
        print(f"✅ Saved merged file → {combined_path}")
    else:
        print("⚠️ No data collected from any league.")

    print(f"🏁 Completed at {datetime.now():%Y-%m-%d %H:%M:%S}")

if __name__ == "__main__":
    main()
