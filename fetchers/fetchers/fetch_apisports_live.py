import os
import requests
import pandas as pd
from datetime import datetime

# ---------------- CONFIG ----------------
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

# ---------------- UTILITIES ----------------
def fetch_json(url, params=None):
    """Safe request wrapper for API-Sports."""
    print(f"\n🔎 DEBUG → Fetching {url} with {params}", flush=True)
    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=15)
        print(f"🔎 DEBUG → HTTP {r.status_code}", flush=True)
        if r.status_code != 200:
            print("❌ DEBUG → Non-200 response, returning empty dict", flush=True)
            return {}
        data = r.json()
        print(f"🔎 DEBUG → Keys: {list(data.keys())}", flush=True)
        if not data.get("response"):
            print("⚠️ DEBUG → Empty response array", flush=True)
        else:
            print(f"✅ DEBUG → Response length: {len(data.get('response', []))}", flush=True)
        return data
    except Exception as e:
        print(f"❌ DEBUG → Request failed: {e}", flush=True)
        return {}

# ---------------- STANDINGS ----------------
def fetch_standings(league_name, league_id, season):
    """Fetch standings (wins/losses/points) for football leagues."""
    print(f"\n🏈 DEBUG → Requesting standings for {league_name} ({league_id}) season={season}", flush=True)
    url = "https://v1.american-football.api-sports.io/standings"
    data = fetch_json(url, {"league": league_id, "season": season})

    if not data.get("response"):
        print(f"⚠️ DEBUG → {league_name}: no standings returned.", flush=True)
        return pd.DataFrame()

    rows = []
    for t in data["response"]:
        team = t.get("team", {}).get("name")
        if not team:
            continue
        pts = t.get("points", {})
        rows.append({
            "league": league_name,
            "team": team,
            "wins": t.get("won"),          # ✅ FIXED (was games.won)
            "losses": t.get("lost"),
            "ties": t.get("ties"),
            "points_for": pts.get("for"),
            "points_against": pts.get("against"),
        })

    df = pd.DataFrame(rows)
    print(f"✅ DEBUG → {league_name} standings shape: {df.shape}", flush=True)
    print(df.head(5))
    return df

# ---------------- TEAMS ----------------
def fetch_teams(sport, league_id, season):
    """Fetch team metadata for non-football leagues."""
    print(f"\n🏀 DEBUG → Requesting teams for {sport.upper()} league_id={league_id}, season={season}", flush=True)
    url = f"https://v1.{sport}.api-sports.io/teams"
    data = fetch_json(url, {"league": league_id, "season": season})
    if not data.get("response"):
        print(f"⚠️ DEBUG → {sport.upper()} {season}: no data returned.", flush=True)
        return pd.DataFrame()
    df = pd.json_normalize(data["response"])
    print(f"✅ DEBUG → {sport.upper()} {season}: {len(df)} teams.", flush=True)
    return df

# ---------------- MAIN ----------------
def main():
    print(f"\n🚀 DEBUG → Starting API-Sports fetcher at {datetime.now():%Y-%m-%d %H:%M:%S}", flush=True)
    print(f"DEBUG → API Key prefix: {API_KEY[:6]}...", flush=True)
    print(f"DEBUG → Leagues to fetch: {LEAGUES}", flush=True)

    all_dfs = []

    for league, (sport, league_id) in LEAGUES.items():
        print(f"\n🔹 DEBUG → Fetching {league} ({sport})...", flush=True)
        if sport == "american-football":
            df = fetch_standings(league, league_id, 2025)
        else:
            df = fetch_teams(sport, league_id, 2025)

        if df.empty:
            print(f"⚠️ DEBUG → {league}: no data retrieved.\n", flush=True)
            continue

        out_path = os.path.join(DATA_DIR, f"{league.lower()}_stats.csv")
        df.to_csv(out_path, index=False)
        print(f"💾 DEBUG → Saved {out_path} ({len(df)} rows)", flush=True)
        all_dfs.append(df)

    if all_dfs:
        combined = pd.concat(all_dfs, ignore_index=True)
        combined_path = os.path.join(DATA_DIR, "team_stats_latest.csv")
        combined.to_csv(combined_path, index=False)
        print(f"\n🎉 DEBUG → Combined {len(combined)} rows across {len(all_dfs)} leagues.")
        print(f"✅ DEBUG → Saved merged file → {combined_path}")
    else:
        print("⚠️ DEBUG → No leagues returned any data.", flush=True)

    print(f"🏁 DEBUG → Completed at {datetime.now():%Y-%m-%d %H:%M:%S}", flush=True)

if __name__ == "__main__":
    main()
