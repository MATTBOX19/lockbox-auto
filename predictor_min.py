# predictor_min.py — LockBox Pro (3-day lookahead edition)
import os, sys, time, json, datetime
import pandas as pd
import numpy as np
import requests

OUTPUT_DIR = os.getenv("OUTPUT_DIR", "/opt/render/project/src/Output")
API_KEY = os.getenv("ODDS_API_KEY", "")
BASE_URL = "https://api.the-odds-api.com/v4/sports"

# how many days ahead to include
LOOKAHEAD_DAYS = int(os.getenv("LOOKAHEAD_DAYS", "3"))

# helper to safely create folders
os.makedirs(OUTPUT_DIR, exist_ok=True)

def fetch_events(sport_key):
    """Fetch upcoming events for a given sport."""
    params = {
        "apiKey": API_KEY,
        "regions": "us",
        "markets": "h2h,spreads,totals",
        "oddsFormat": "american"
    }
    url = f"{BASE_URL}/{sport_key}/odds"
    try:
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
        events = []
        cutoff = datetime.datetime.utcnow() + datetime.timedelta(days=LOOKAHEAD_DAYS)
        for ev in data:
            start = datetime.datetime.fromisoformat(ev["commence_time"].replace("Z",""))
            if start > cutoff:
                continue
            events.append(ev)
        print(f"📊 Retrieved {len(events)} events for {sport_key}")
        return events
    except Exception as e:
        print(f"⚠️ Error fetching {sport_key}: {e}")
        return []

def implied_prob_from_odds(odds):
    """Convert American odds to implied probability."""
    try:
        o = float(odds)
        if o > 0: return 100 / (o + 100)
        else: return abs(o) / (abs(o) + 100)
    except: return np.nan

def analyze_event(ev):
    """Simple model stub — estimate which team covers."""
    try:
        sport = ev.get("sport_key","")
        teams = ev.get("teams",[])
        if len(teams) < 2: return None
        home_team = ev.get("home_team", teams[-1])
        away_team = [t for t in teams if t != home_team][0]
        markets = ev.get("bookmakers",[])
        if not markets: return None
        odds_data = markets[0].get("markets", [])
        moneyline = next((m for m in odds_data if m["key"]=="h2h"), None)
        spreads = next((m for m in odds_data if m["key"]=="spreads"), None)
        totals = next((m for m in odds_data if m["key"]=="totals"), None)

        pick, edge, conf = "No Pick", 0.0, 50.0
        if moneyline and len(moneyline["outcomes"])==2:
            o1,o2 = moneyline["outcomes"]
            p1 = implied_prob_from_odds(o1["price"])
            p2 = implied_prob_from_odds(o2["price"])
            pick = o1["name"] if p1>p2 else o2["name"]
            edge = round(abs(p1-p2)*100,2)
            conf = round(max(p1,p2)*100,2)

        reason = f"Auto pick based on ML odds difference ({edge:.2f} edge)"
        return {
            "Sport": sport,
            "GameTime": ev["commence_time"],
            "Team1": away_team,
            "Team2": home_team,
            "MoneylinePick": pick,
            "Confidence": conf,
            "Edge": edge,
            "ML": f"{away_team}:{moneyline['outcomes'][0]['price']} | {home_team}:{moneyline['outcomes'][1]['price']}" if moneyline else "",
            "ATS": spreads["key"] if spreads else "",
            "OU": totals["key"] if totals else "",
            "Reason": reason,
            "LockEmoji": "🔒" if edge>=0.5 and conf>=75 else "",
            "UpsetEmoji": "💥" if edge>=0.3 and pick==away_team else "",
        }
    except Exception as e:
        print(f"⚠️ Error analyzing event: {e}")
        return None

def main():
    all_sports = [
        "americanfootball_nfl",
        "americanfootball_ncaaf",
        "basketball_nba",
        "icehockey_nhl",
        "baseball_mlb",
    ]
    all_rows=[]
    for s in all_sports:
        events = fetch_events(s)
        for ev in events:
            row = analyze_event(ev)
            if row: all_rows.append(row)

    if not all_rows:
        print("⚠️ No valid games found in next few days — writing empty file.")
    df = pd.DataFrame(all_rows)
    timestamp = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    latest_path = os.path.join(OUTPUT_DIR, "Predictions_latest_Explained.csv")
    dated_path  = os.path.join(OUTPUT_DIR, f"Predictions_{timestamp}_Explained.csv")

    df.to_csv(latest_path, index=False)
    df.to_csv(dated_path, index=False)

    print(f"✅ Wrote {len(df)} rows to {dated_path}")
    print(f"✅ Updated {latest_path}")

if __name__ == "__main__":
    main()
