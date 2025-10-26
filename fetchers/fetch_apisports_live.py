import os
import requests
import pandas as pd
from datetime import datetime
import time

API_KEY = os.getenv("APISPORTS_KEY")
if not API_KEY:
    raise EnvironmentError("Missing $APISPORTS_KEY environment variable.")

HEADERS = {"x-apisports-key": API_KEY}

# league name → (sport type, league id)
LEAGUES = {
    "nfl": ("american-football", 1),
    "ncaaf": ("american-football", 2),
    "nba": ("basketball", 12),
    "mlb": ("baseball", 1),
    "nhl": ("hockey", 57),
}

DATA_DIR = "Data"
os.makedirs(DATA_DIR, exist_ok=True)

def fetch_teams(sport: str, league_id: int, season=2025) -> pd.DataFrame:
    """Fetch base team info for the league."""
    url = f"https://v1.{sport}.api-sports.io/teams"
    params = {"league": league_id, "season": season}
    print(f"📊 Fetching {sport.upper()} teams...")
    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=20)
        data = r.json()
    except Exception as e:
        print(f"❌ {sport.upper()} teams request failed: {e}")
        return pd.DataFrame()

    if not data.get("response"):
        print(f"⚠️ {sport.upper()}: No team data returned.")
        return pd.DataFrame()

    df = pd.json_normalize(data["response"])
    df["league_id"] = league_id
    df["sport"] = sport
    return df


def fetch_team_stats(sport: str, league_id: int, team_id: int, season=2025) -> dict:
    """Fetch statistics per team (if supported by API-Sports)."""
    url = f"https://v1.{sport}.api-sports.io/teams/statistics"
    params = {"league": league_id, "season": season, "team": team_id}
    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=20)
        data = r.json()
        if not data.get("response"):
            return {}
        stats = data["response"]
        stats["team_id"] = team_id
        stats["sport"] = sport
        return stats
    except Exception:
        return {}


def fetch_league_with_stats(league: str, sport: str, league_id: int, season=2025) -> pd.DataFrame:
    """Fetch team info and try to enrich with statistics."""
    teams_df = fetch_teams(sport, league_id, season)
    if teams_df.empty:
        print(f"⚠️ {league.upper()}: No teams found — skipping stats.")
        return pd.DataFrame()

    all_stats = []
    for _, row in teams_df.iterrows():
        tid = row.get("id") or row.get("team.id")
        if not tid:
            continue
        stats = fetch_team_stats(sport, league_id, tid, season)
        if stats:
            base = {
                "league": league.upper(),
                "team_id": tid,
                "team": row.get("name") or row.get("team.name"),
                "city": row.get("city") or "",
            }
            # Extract key performance metrics if available
            team_stats = {
                "games_played": stats.get("games", {}).get("played"),
                "wins": stats.get("games", {}).get("wins", {}).get("total")
                if isinstance(stats.get("games", {}).get("wins"), dict)
                else None,
                "losses": stats.get("games", {}).get("loses", {}).get("total")
                if isinstance(stats.get("games", {}).get("loses"), dict)
                else None,
                "points_for": stats.get("points", {}).get("for", {}).get("total")
                if isinstance(stats.get("points", {}).get("for"), dict)
                else None,
                "points_against": stats.get("points", {}).get("against", {}).get("total")
                if isinstance(stats.get("points", {}).get("against"), dict)
                else None,
            }
            all_stats.append({**base, **team_stats})
        time.sleep(0.5)  # gentle rate-limit

    if not all_stats:
        print(f"⚠️ {league.upper()}: No stats found; saving team info only.")
        teams_df.to_csv(os.path.join(DATA_DIR, f"{league}_team_stats.csv"), index=False)
        return teams_df

    df_stats = pd.DataFrame(all_stats)
    df_stats.to_csv(os.path.join(DATA_DIR, f"{league}_team_stats.csv"), index=False)
    print(f"✅ {league.upper()}: {len(df_stats)} teams with stats.")
    return df_stats


def main():
    all_dfs = []

    for league, (sport, league_id) in LEAGUES.items():
        print(f"🏈 Fetching league: {league.upper()} ({sport})")
        df = fetch_league_with_stats(league, sport, league_id)
        if not df.empty:
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
