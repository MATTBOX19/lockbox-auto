import os
import requests
import pandas as pd
from datetime import datetime

# ------------------- CONFIG -------------------
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

# ------------------- HELPERS -------------------
def fetch_json(url, params=None):
    """Safe request wrapper for API-Sports"""
    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"❌ Request failed: {e}")
        return {}

def fetch_standings(league_name, league_id, season):
    """Fetch standings for football leagues (NFL, NCAAF)."""
    url = "https://v1.american-football.api-sports.io/standings"
    data = fetch_json(url, {"league": league_id, "season": season})
    if not data.get("response"):
        print(f"⚠️ {league_name} standings empty for {season}.")
        return pd.DataFrame()

    rows = []
    for t in data["response"]:
        team = t.get("team", {}).get("name")
        if not team:
            continue
        rows.append({
            "league": league_name,
            "team": team,
            "wins": t.get("won"),
            "losses": t.get("lost"),
            "ties": t.get("ties"),
            "points_for": t.get("points", {}).get("for"),
            "points_against": t.get("points", {}).get("against"),
        })
    df = pd.DataFrame(rows)
    if not df.empty:
        df["games_played"] = df[["wins", "losses", "ties"]].fillna(0).sum(axis=1)
        df["win_pct"] = (df["wins"] / df["games_played"]).round(3)
        print(f"📊 {league_name}: {len(df)} standings records.")
    return df

def fetch_teams(sport, league_id, season):
    """Fetch team metadata for non-football leagues."""
    url = f"https://v1.{sport}.api-sports.io/teams"
    data = fetch_json(url, {"league": league_id, "season": season})
    if not data.get("response"):
        print(f"⚠️ {sport.upper()} ({season}) teams missing.")
        return pd.DataFrame()
    df = pd.json_normalize(data["response"])
    print(f"✅ {sport.upper()} {season}: {len(df)} teams.")
    return df

# ------------------- MAIN -------------------
def main():
    all_dfs = []
    print("🏁 Starting API-Sports data fetcher...\n")

    for league, (sport, league_id) in LEAGUES.items():
        print(f"🔹 Fetching {league} ({sport})...")

        if sport == "american-football":
            df = fetch_standings(league, league_id, 2025)
        else:
            df = fetch_teams(sport, league_id, 2025)

        if not df.empty:
            out_path = os.path.join(DATA_DIR, f"{league.lower()}_stats.csv")
            df.to_csv(out_path, index=False)
            all_dfs.append(df)
            print(f"💾 Saved {league} stats → {out_path}")
        else:
            print(f"⚠️ {league}: no data found.")

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
