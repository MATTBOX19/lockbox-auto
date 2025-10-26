import os, requests, pandas as pd
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
    """Request with live logging and 8-second timeout."""
    print(f"→ Fetching {url.split('//')[1]} {params}", flush=True)
    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=8)
        print(f"↳ HTTP {r.status_code}", flush=True)
        if r.status_code != 200:
            return {}
        data = r.json()
        if not data.get("response"):
            print("⚠️ Empty response.", flush=True)
        return data
    except requests.Timeout:
        print("⏱️ Request timed out.", flush=True)
        return {}
    except Exception as e:
        print(f"❌ Error: {e}", flush=True)
        return {}

def fetch_teams(sport, league_id, season):
    url = f"https://v1.{sport}.api-sports.io/teams"
    data = fetch_json(url, {"league": league_id, "season": season})
    if not data.get("response"):
        print(f"⚠️ {sport.upper()} teams missing for {season}.", flush=True)
        return pd.DataFrame()
    df = pd.json_normalize(data["response"])
    print(f"✅ {sport.upper()} {season}: {len(df)} teams.", flush=True)
    return df

def fetch_standings(league, league_id, season):
    url = "https://v1.american-football.api-sports.io/standings"
    data = fetch_json(url, {"league": league_id, "season": season})
    if not data.get("response"):
        print(f"⚠️ {league}: standings empty.", flush=True)
        return pd.DataFrame()
    rows = []
    for t in data["response"]:
        team = t.get("team", {}).get("name")
        if not team: continue
        g = t.get("games", {})
        rows.append({
            "league": league, "team": team,
            "wins": g.get("won"), "losses": g.get("lost"), "ties": g.get("ties"),
            "points_for": t.get("points", {}).get("for"),
            "points_against": t.get("points", {}).get("against")
        })
    df = pd.DataFrame(rows)
    if not df.empty:
        df["games_played"] = df[["wins","losses","ties"]].fillna(0).sum(axis=1)
        df["win_pct"] = (df["wins"]/df["games_played"]).round(3)
        print(f"📊 {league}: {len(df)} standings.", flush=True)
    return df

def fetch_games(league, league_id, season):
    url = "https://v1.american-football.api-sports.io/games"
    data = fetch_json(url, {"league": league_id, "season": season})
    if not data.get("response"):
        print(f"⚠️ {league}: no games.", flush=True)
        return pd.DataFrame()
    rows = []
    for g in data["response"]:
        tms, scr = g.get("teams", {}), g.get("scores", {})
        for side in ["home", "away"]:
            team = tms.get(side)
            s = scr.get(side)
            if not team or s is None: continue
            rows.append({"league": league, "team": team.get("name"), "points": s})
    df = pd.DataFrame(rows)
    if not df.empty:
        out = df.groupby(["league","team"]).agg(
            games_played=("points","count"), avg_points=("points","mean")
        ).reset_index()
        print(f"🏈 {league}: {len(out)} teams aggregated.", flush=True)
        return out
    return pd.DataFrame()

def main():
    print(f"🏁 Starting fetch at {datetime.now():%Y-%m-%d %H:%M:%S}", flush=True)
    all_dfs = []
    for league, (sport, lid) in LEAGUES.items():
        print(f"\n🔹 {league} ({sport})", flush=True)
        if sport == "american-football":
            s = fetch_standings(league, lid, 2025)
            g = fetch_games(league, lid, 2025)
            merged = pd.merge(s, g, on=["league","team"], how="left")
            if merged.empty: continue
            path = os.path.join(DATA_DIR, f"{league.lower()}_stats.csv")
            merged.to_csv(path, index=False)
            all_dfs.append(merged)
            print(f"💾 Saved {path}", flush=True)
        else:
            df = fetch_teams(sport, lid, 2025)
            if df.empty: continue
            path = os.path.join(DATA_DIR, f"{league.lower()}_team_stats.csv")
            df.to_csv(path, index=False)
            all_dfs.append(df)
            print(f"💾 Saved {path}", flush=True)
    if not all_dfs:
        print("⚠️ Nothing fetched.", flush=True)
        return
    combined = pd.concat(all_dfs, ignore_index=True)
    out_path = os.path.join(DATA_DIR, "team_stats_latest.csv")
    combined.to_csv(out_path, index=False)
    print(f"\n🎉 Combined {len(combined)} rows. ✅ {out_path}", flush=True)
    print(f"🕒 Done {datetime.now():%Y-%m-%d %H:%M:%S}", flush=True)

if __name__ == "__main__":
    main()
