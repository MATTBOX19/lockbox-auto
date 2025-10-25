import os
import requests
import pandas as pd
from datetime import datetime

# Load API key from environment
API_KEY = os.getenv("APISPORTS_KEY")
HEADERS = {"x-apisports-key": API_KEY}

# Define leagues: (sport, league_id)
LEAGUES = {
    "NFL": ("american-football", 1),
    "NCAAF": ("american-football", 2),
    "NBA": ("basketball", 12),
    "MLB": ("baseball", 1),
    "NHL": ("hockey", 57),
}

def fetch_teams(sport, league_id, season=2025):
    """Fetch team data for a given sport/league from API-Sports"""
    url = f"https://v1.{sport}.api-sports.io/teams"
    params = {"league": league_id, "season": season}

    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=15)
        data = r.json()

        # Handle no data returned
        if "response" not in data or not data["response"]:
            # Try fallback for NBA
            if sport == "basketball":
                print(f"⚠️ {sport.upper()} {season}: No data. Trying fallback season 2024...")
                params["season"] = 2024
                r2 = requests.get(url, headers=HEADERS, params=params, timeout=15)
                data2 = r2.json()
                if "response" in data2 and data2["response"]:
                    df = pd.json_normalize(data2["response"])
                    print(f"✅ {sport.upper()} fallback succeeded: {len(df)} teams (2024 season).")
                    return df
                else:
                    print(f"⚠️ {sport.upper()} API currently empty for both 2025 and 2024. Will retry later.")
                    return pd.DataFrame()
            else:
                print(f"⚠️ {sport.upper()}: No data returned.")
                if "errors" in data and data["errors"]:
                    print("  Raw errors:", data["errors"])
                return pd.DataFrame()

        # Data found
        df = pd.json_normalize(data["response"])
        print(f"✅ {sport.upper()}: {len(df)} teams fetched.")
        return df

    except Exception as e:
        print(f"❌ {sport.upper()} fetch failed:", e)
        return pd.DataFrame()

def main():
    """Main routine: fetch all league data and combine"""
    all_dfs = []
    os.makedirs("Data", exist_ok=True)

    for league, (sport, league_id) in LEAGUES.items():
        print(f"📊 Fetching {league} data...")
        df = fetch_teams(sport, league_id)
        if not df.empty:
            csv_path = f"Data/{league.lower()}_team_stats.csv"
            df.to_csv(csv_path, index=False)
            print(f"💾 Saved {league} data → {csv_path}")
            all_dfs.append(df)

    if not all_dfs:
        print("⚠️ No leagues returned data.")
        return

    # Combine and save
    combined = pd.concat(all_dfs, ignore_index=True)
    combined.to_csv("Data/team_stats_latest.csv", index=False)

    print(f"\n🎉 Combined {len(combined)} total teams across {len(all_dfs)} leagues")
    print("✅ Saved merged file → Data/team_stats_latest.csv")
    print(f"🕒 Completed at {datetime.now():%Y-%m-%d %H:%M:%S}")

if __name__ == "__main__":
    main()
