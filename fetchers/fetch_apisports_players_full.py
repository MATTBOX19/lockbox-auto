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

# league: (sport domain, league id)
LEAGUES = {
    "nfl": ("american-football", 1),
    "ncaaf": ("american-football", 2),
    "nba": ("basketball", 12),
    "mlb": ("baseball", 1),
    "nhl": ("hockey", 57),
}

def fetch_team_ids(sport: str, league_id: int, season=2025):
    """Fetch all team IDs for a given league."""
    url = f"https://v1.{sport}.api-sports.io/teams"
    params = {"league": league_id, "season": season}
    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=20)
        data = r.json()
        teams = [t["team"]["id"] for t in data.get("response", []) if t.get("team")]
        return teams
    except Exception as e:
        print(f"⚠️ Failed to fetch team IDs for {sport}: {e}")
        return []

def fetch_players_for_team(sport: str, team_id: int, season=2025):
    """Fetch player roster for a given team."""
    url = f"https://v1.{sport}.api-sports.io/players"
    params = {"team": team_id, "season": season}
    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=20)
        data = r.json()
        players = data.get("response", [])
        return players
    except Exception as e:
        print(f"❌ {sport.upper()} team {team_id} player fetch failed: {e}")
        return []

def normalize_players(players, league):
    """Normalize player JSON into flat rows."""
    rows = []
    for p in players:
        player = p.get("player", p)
        rows.append({
            "league": league.upper(),
            "player_id": player.get("id"),
            "name": player.get("name"),
            "age": player.get("age"),
            "height": player.get("height"),
            "weight": player.get("weight"),
            "college": player.get("college"),
            "position": player.get("position"),
            "number": player.get("number"),
            "team_id": p.get("team", {}).get("id") if p.get("team") else None,
            "team_name": p.get("team", {}).get("name") if p.get("team") else None,
            "experience": player.get("experience"),
            "group": player.get("group"),
            "salary": player.get("salary"),
            "image": player.get("image"),
        })
    return pd.DataFrame(rows)

def main():
    all_sports = []
    for league, (sport, league_id) in LEAGUES.items():
        print(f"\n🏈 Processing league: {league.upper()} ({sport}, id={league_id})")
        team_ids = fetch_team_ids(sport, league_id)
        if not team_ids:
            print(f"⚠️ No teams returned for {league.upper()}")
            continue

        all_players = []
        for tid in team_ids:
            print(f"📊 Fetching {sport.upper()} players for team {tid}...")
            players = fetch_players_for_team(sport, tid)
            if not players:
                continue
            df = normalize_players(players, league)
            all_players.append(df)
            time.sleep(0.6)  # rate-limit

        if not all_players:
            print(f"⚠️ {league.upper()}: No players returned — skipping.")
            continue

        combined = pd.concat(all_players, ignore_index=True)
        out_path = os.path.join(DATA_DIR, f"{league}_players_2025.csv")
        combined.to_csv(out_path, index=False)
        print(f"✅ {league.upper()}: wrote {len(combined)} rows to {out_path}")
        all_sports.append(combined)

    if all_sports:
        merged = pd.concat(all_sports, ignore_index=True)
        merged.to_csv(os.path.join(DATA_DIR, "players_all_latest.csv"), index=False)
        print(f"\n🎉 Combined {len(merged)} total players across {len(all_sports)} leagues.")
    else:
        print("⚠️ No player data fetched from any league.")

    print(f"🕒 Completed at {datetime.utcnow().isoformat()} UTC")

if __name__ == "__main__":
    main()
