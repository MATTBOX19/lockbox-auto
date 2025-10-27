import os
import requests
import pandas as pd
import time
from datetime import datetime

API_KEY = os.getenv("APISPORTS_KEY")
if not API_KEY:
    raise EnvironmentError("Missing $APISPORTS_KEY environment variable.")

HEADERS = {"x-apisports-key": API_KEY}
DATA_DIR = "Data"
os.makedirs(DATA_DIR, exist_ok=True)

LEAGUES = {
    "nfl": ("american-football", 1),
    "ncaaf": ("american-football", 2),
}

def fetch_players(sport: str, league_id: int, season=2025) -> pd.DataFrame:
    """Fetch player rosters for given league."""
    url = f"https://v1.{sport}.api-sports.io/players"
    params = {"league": league_id, "season": season}
    print(f"📊 Fetching {sport.upper()} player rosters for league={league_id} season={season}...")
    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=20)
        data = r.json()
        if not data.get("response"):
            print(f"⚠️ No player roster returned for {sport.upper()} season={season}")
            return pd.DataFrame()
        df = pd.json_normalize(data["response"])
        df["season"] = season
        df["league_id"] = league_id
        df["sport"] = sport
        return df
    except Exception as e:
        print(f"❌ Error fetching players: {e}")
        return pd.DataFrame()


def fetch_player_stats(sport: str, league_id: int, player_id: int, season: int) -> dict:
    """Fetch individual player statistics (historical)."""
    url = f"https://v1.{sport}.api-sports.io/players/statistics"
    params = {"id": player_id, "season": season}
    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=20)
        data = r.json()
        if not data.get("response"):
            return {}
        stats = data["response"]
        stats["player_id"] = player_id
        stats["season"] = season
        stats["league_id"] = league_id
        stats["sport"] = sport
        return stats
    except Exception:
        return {}


def merge_players_and_stats(players_df: pd.DataFrame, sport: str, league_id: int) -> pd.DataFrame:
    """Try to merge available stats for roster players (from recent historical seasons)."""
    all_stats = []
    for _, row in players_df.iterrows():
        pid = row.get("id") or row.get("player.id")
        if not pid:
            continue
        # loop back through 2025→2022 until data found
        for season in range(2025, 2021, -1):
            stats = fetch_player_stats(sport, league_id, pid, season)
            if stats:
                stats_flat = {"player_id": pid, "season": season}
                stats_flat.update(stats)
                all_stats.append(stats_flat)
                break
        time.sleep(0.5)

    if not all_stats:
        print(f"⚠️ No player statistics found for {sport.upper()} — keeping roster only.")
        return players_df

    df_stats = pd.json_normalize(all_stats)
    merged = pd.merge(players_df, df_stats, left_on="id", right_on="player_id", how="left")
    return merged


def main():
    all_data = []
    for league, (sport, league_id) in LEAGUES.items():
        print(f"\n🏈 Processing league: {league.upper()} ({sport}, id={league_id})")

        roster = fetch_players(sport, league_id)
        if roster.empty:
            print(f"⚠️ {league.upper()}: No players returned — skipping.")
            continue

        merged = merge_players_and_stats(roster, sport, league_id)
        out_path = os.path.join(DATA_DIR, f"{league}_players.csv")
        merged.to_csv(out_path, index=False)
        print(f"✅ {league.upper()}: wrote {len(merged)} rows to {out_path}")
        all_data.append(merged)

    if all_data:
        combined = pd.concat(all_data, ignore_index=True)
        combined.to_csv(os.path.join(DATA_DIR, "players_combined.csv"), index=False)
        print(f"🎉 Combined {len(combined)} total player rows across leagues.")
    else:
        print("⚠️ No player data fetched from any league.")

    print(f"🕒 Completed at {datetime.utcnow().isoformat()} UTC")


if __name__ == "__main__":
    main()
