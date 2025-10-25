import os
import requests
import pandas as pd
from datetime import datetime

API_KEY = os.getenv("APISPORTS_KEY")
HEADERS = {"x-apisports-key": API_KEY}

LEAGUES = {
    "NFL": ("american-football", 1),
    "NCAAF": ("american-football", 2),
    "NBA": ("basketball", 12),
    "MLB": ("baseball", 1),
    "NHL": ("hockey", 57),
}

def fetch_teams(sport, league_id, season=2025):
    """Fetch team data from API-Sports for a given league and season."""
    url = f"https://v1.{sport}.api-sports.io/teams"
    params = {"league": league_id, "season": season}
    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=15)
        data = r.json()
        if "response" not in data or not data["response"]:
            print(f"⚠️ {sport.upper()}: No data returned for season {season}.")
            if "errors" in data:
                print("  Raw errors:", data["errors"])
            return pd.DataFrame()
        df = pd.json_normalize(data["response"])
        print(f"✅ {sport.upper()} {season}: {len(df)} teams fetched.")
        return df
    except Exception as e:
        print(f"❌ {sport.upper()} fetch failed:", e)
        return pd.DataFrame()

def main():
    """Fetch data for all configured leagues and save combined output."""
    all_dfs = []
    os.makedirs("Data", exist_ok=True)

    for league, (sport, league_id) in LEAGUES.items():
        print(f"\n📊 Fetching {league} data...")
        df = fetch_teams(sport, league_id, season=2025)

        # Fallback for NBA if 2025 is not yet live
        if league == "NBA" and df.empty:
            print("🔄 NBA 2025 returned empty — retrying with 2024 season...")
            df = fetch_teams(sport, league_id, season=2024)

        if not df.empty:
            csv_path = f"Data/{league.lower()}_team_stats.csv"
            df.to_csv(csv_path, index=False)
            print(f"💾 Saved {league} data → {csv_path}")
            all_dfs.append(df)
        else:
            print(f"⚠️ Skipped {league} — no valid data retrieved.")

    if not all_dfs:
        print("\n⚠️ No leagues returned any data. Check API key or limits.")
        return

    combined = pd.concat(all_dfs, ignore_index=True)
    combined.to_csv("Data/team_stats_latest.csv", index=False)
    print(f"\n🎉 Combined {len(combined)} total teams across {len(all_dfs)} leagues")
    print("✅ Saved merged file → Data/team_stats_latest.csv")
    print(f"🕒 Completed at {datetime.now():%Y-%m-%d %H:%M:%S}")

if __name__ == "__main__":
    main()
