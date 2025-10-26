import os
import requests
import pandas as pd
from datetime import datetime

# --- Setup ---
API_KEY = os.getenv("APISPORTS_KEY")
if not API_KEY:
    raise EnvironmentError("Missing $APISPORTS_KEY environment variable.")
HEADERS = {"x-apisports-key": API_KEY}

DATA_DIR = "Data"
os.makedirs(DATA_DIR, exist_ok=True)

# --- Leagues configuration ---
LEAGUES = {
    "NFL": ("american-football", 1),
    "NCAAF": ("american-football", 2),
    "NBA": ("basketball", 12),
    "MLB": ("baseball", 1),
    "NHL": ("hockey", 57),
}

# --- Helper functions ---
def fetch_json(url, params=None):
    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=30)
        return r.json()
    except Exception as e:
        print(f"❌ Request failed: {e}")
        return {}

def fetch_teams(sport, league_id, season):
    """Fetch team metadata for non-football leagues."""
    url = f"https://v1.{sport}.api-sports.io/teams"
    data = fetch_json(url, {"league": league_id, "season": season})
    if not data.get("response"):
        print(f"⚠️ {sport.upper()} ({season}) teams missing.")
        # try 2024 fallback for basketball
        if sport == "basketball" and season == 2025:
            print(f"↩️ Retrying {sport.upper()} for 2024 season...")
            return fetch_teams(sport, league_id, 2024)
        return pd.DataFrame()
    df = pd.json_normalize(data["response"])
    print(f"✅ {sport.upper()} {season}: {len(df)} teams.")
    return df

def fetch_standings(league_name, league_id, season):
    """Fetch standings (wins/losses/points) for football leagues."""
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
        games = t.get("games", {})
        rows.append({
            "league": league_name,
            "team": team,
            "wins": games.get("won"),
            "losses": games.get("lost"),
            "ties": games.get("ties"),
            "points_for": t.get("points", {}).get("for"),
            "points_against": t.get("points", {}).get("against"),
        })
    df = pd.DataFrame(rows)
    if not df.empty:
        df["games_played"] = df[["wins", "losses", "ties"]].fillna(0).sum(axis=1)
        df["win_pct"] = (df["wins"] / df["games_played"]).round(3)
        print(f"📊 {league_name}: {len(df)} standings records.")
    return df

def fetch_games(league_name, league_id, season):
    """Fetch game-level scoring data for football leagues."""
    url = "https://v1.american-football.api-sports.io/games"
    data = fetch_json(url, {"league": league_id, "season": season})
    if not data.get("response"):
        print(f"⚠️ {league_name}: No games found for {season}.")
        return pd.DataFrame()

    rows = []
    for g in data["response"]:
        teams = g.get("teams", {})
        scores = g.get("scores", {})
        for side in ["home", "away"]:
            t = teams.get(side)
            s = scores.get(side)
            if not t or s is None:
                continue
            rows.append({
                "league": league_name,
                "team": t.get("name"),
                "points": s,
                "season": season,
            })

    df = pd.DataFrame(rows)
    if not df.empty:
        summary = df.groupby(["league", "team"]).agg(
            games_played=("points", "count"),
            avg_points=("points", "mean")
        ).reset_index()
        print(f"🏈 {league_name}: {len(summary)} teams aggregated from {len(df)} games.")
        return summary
    return pd.DataFrame()

# --- Main process ---
def main():
    all_dfs = []
    print("🏁 Starting API-Sports data fetcher...\n")

    for league, (sport, league_id) in LEAGUES.items():
        print(f"🔹 Fetching {league} ({sport})...")

        if sport == "american-football":
            # NFL / NCAAF: standings + games
            standings_df = fetch_standings(league, league_id, 2025)
            games_df = fetch_games(league, league_id, 2025)
            merged = pd.merge(standings_df, games_df, on=["league", "team"], how="left")
            if not merged.empty:
                out_path = os.path.join(DATA_DIR, f"{league.lower()}_stats.csv")
                merged.to_csv(out_path, index=False)
                all_dfs.append(merged)
                print(f"💾 Saved {league} stats → {out_path}")
            else:
                print(f"⚠️ {league}: no merged stats found.")
        else:
            # NBA/MLB/NHL — team info only
            teams_df = fetch_teams(sport, league_id, 2025)
            if not teams_df.empty:
                out_path = os.path.join(DATA_DIR, f"{league.lower()}_team_stats.csv")
                teams_df.to_csv(out_path, index=False)
                all_dfs.append(teams_df)
                print(f"💾 Saved {league} data → {out_path}")
            else:
                print(f"⚠️ {league}: no team data returned.")

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
