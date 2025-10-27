#!/usr/bin/env python3
"""
LockBox – API-Sports Odds Builder
Replaces The Odds API with API-Sports for all major leagues.
"""

import os, requests, pandas as pd, datetime as dt

API_KEY = os.getenv("API_SPORTS_KEY", "")
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "/opt/render/project/src/Output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# --- Config for each sport
SPORTS = {
    "americanfootball_nfl": {
        "domain": "v1.american-football.api-sports.io",
        "league": 1,      # NFL
        "season": 2025
    },
    "americanfootball_ncaaf": {
        "domain": "v1.american-football.api-sports.io",
        "league": 2,      # NCAAF
        "season": 2025
    },
    "basketball_nba": {
        "domain": "v1.basketball.api-sports.io",
        "league": 12,     # NBA
        "season": 2025
    },
    "baseball_mlb": {
        "domain": "v1.baseball.api-sports.io",
        "league": 1,      # MLB
        "season": 2025
    },
    "icehockey_nhl": {
        "domain": "v1.hockey.api-sports.io",
        "league": 57,     # NHL
        "season": 2025
    }
}

def log(msg: str):
    print(f"{dt.datetime.utcnow().isoformat()}Z  {msg}", flush=True)

def fetch_odds(sport_key, cfg):
    """Fetch odds feed for given sport."""
    url = f"https://{cfg['domain']}/odds"
    params = {"league": cfg["league"], "season": cfg["season"]}
    headers = {"x-apisports-key": API_KEY}
    try:
        r = requests.get(url, headers=headers, params=params, timeout=20)
        if r.status_code != 200:
            log(f"⚠️  {sport_key} bad status {r.status_code}")
            return []
        data = r.json()
        if not data or not data.get("response"):
            log(f"⚠️  {sport_key} empty response")
            return []
        log(f"📊 {sport_key}: {len(data['response'])} events")
        return data["response"]
    except Exception as e:
        log(f"❌ {sport_key} error {e}")
        return []

def parse_events(sport_key, events):
    """Flatten each event into a row."""
    rows = []
    for ev in events:
        game = ev.get("game", {})
        teams = ev.get("bookmakers", [])[0].get("bets", [])[0].get("values", []) if ev.get("bookmakers") else []
        if not teams or len(teams) < 2:
            continue
        home_team = teams[0].get("value", "")
        away_team = teams[1].get("value", "")
        try:
            home_odd = float(teams[0].get("odd", 0))
            away_odd = float(teams[1].get("odd", 0))
        except:
            continue
        rows.append({
            "Sport_raw": sport_key,
            "Sport": sport_key.split("_")[-1].upper(),
            "GameID": game.get("id", ""),
            "Team1": home_team,
            "Team2": away_team,
            "MoneylinePick": home_team if home_odd < away_odd else away_team,
            "Edge": round(abs(home_odd - away_odd) / max(home_odd, away_odd), 3),
            "Confidence": round(100 * (1 / min(home_odd, away_odd)), 1),
            "HomeOdd": home_odd,
            "AwayOdd": away_odd
        })
    return rows

def main():
    log("🧠 Building predictions from API-Sports odds")

    all_rows = []
    for sport_key, cfg in SPORTS.items():
        events = fetch_odds(sport_key, cfg)
        if events:
            rows = parse_events(sport_key, events)
            all_rows.extend(rows)

    if not all_rows:
        log("❌ No events processed")
        return

    df = pd.DataFrame(all_rows)
    date_str = dt.datetime.utcnow().strftime("%Y-%m-%d")
    out_today = os.path.join(OUTPUT_DIR, f"Predictions_{date_str}_Explained.csv")
    out_latest = os.path.join(OUTPUT_DIR, "Predictions_latest_Explained.csv")

    df.to_csv(out_today, index=False)
    df.to_csv(out_latest, index=False)
    log(f"✅ Wrote {len(df)} rows → {out_latest}")
    log("🚀 Done — CSV ready for web.")

if __name__ == "__main__":
    main()
