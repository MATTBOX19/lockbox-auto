import os
import requests
import pandas as pd
from datetime import datetime

API_KEY = os.getenv("APISPORTS_KEY")
if not API_KEY:
    raise EnvironmentError("Missing $APISPORTS_KEY environment variable.")

HEADERS = {"x-apisports-key": API_KEY}

LEAGUE_ENDPOINTS = {
    "nfl": "https://v1.american-football.api-sports.io/teams?league=1&season=2025",
    "ncaaf": "https://v1.american-football.api-sports.io/teams?league=2&season=2025",
    "nba": "https://v1.basketball.api-sports.io/teams?league=12&season=2025",
    "mlb": "https://v1.baseball.api-sports.io/teams?league=1&season=2025",
    "nhl": "https://v1.hockey.api-sports.io/teams?league=57&season=2025",
}

DATA_DIR = "Data"
os.makedirs(DATA_DIR, exist_ok=True)

def fetch_league(league_name, url):
    print(f"📊 Fetching {league_name.upper()} data...")
    try:
        response = requests.get(url, headers=HEADERS, timeout=30)
        data = response.json()
    except Exception as e:
        print(f"❌ {league_name.upper()} request failed: {e}")
        return pd.DataFrame()

    if "response" not in data or not data["response"]:
        print(f"⚠️ {league_name.upper()}: No data returned.")
        print(f"  Raw errors: {data.get('errors', 'None')}")
        return pd.DataFrame()

    teams = []
    for t in data["response"]:
        teams.append({
            "league": league_name.upper(),
            "id": t.get("id"),
            "team": t.get("name"),
            "code": t.get("code"),
            "city": t.get("city"),
            "stadium": t.get("stadium"),
            "coach": t.get("coach"),
            "owner": t.get("owner"),
            "established": t.get("established"),
            "logo": t.get("logo"),
        })

    df = pd.DataFrame(teams)
    print(f"✅ {league_name.upper()}: {len(df)} teams fetched.")
    return df

def main():
    all_dfs = []

    for league, url in LEAGUE_ENDPOINTS.items():
        df = fetch_league(league, url)
        if not df.empty:
            out_path = os.path.join(DATA_DIR, f"{league}_team_stats.csv")
            df.to_csv(out_path, index=False)
            print(f"💾 Saved {league.upper()} data → {out_path}")
            all_dfs.append(df)

    if not all_dfs:
        print("⚠️ No leagues returned data. Nothing to merge.")
        return

    combined = pd.concat(all_dfs, ignore_index=True)
    out_path = os.path.join(DATA_DIR, "team_stats_latest.csv")
    combined.to_csv(out_path, index=False)

    print(f"\n🎉 Combined {len(combined)} total teams across {len(all_dfs)} leagues")
    print(f"✅ Saved merged file → {out_path}")
    print(f"🕒 Completed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()
