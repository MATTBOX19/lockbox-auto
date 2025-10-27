#!/usr/bin/env python3
"""
LockBox Pro – Learning Predictor
Auto-grades past picks and adjusts edge/confidence by sport performance.
"""

import os, pandas as pd, requests, datetime as dt, numpy as np, json

OUTPUT_DIR = os.getenv("OUTPUT_DIR", "/opt/render/project/src/Output")
ODDS_API_KEY = os.getenv("ODDS_API_KEY", "")
os.makedirs(OUTPUT_DIR, exist_ok=True)

HISTORY_FILE = os.path.join(OUTPUT_DIR, "history.csv")
PRED_FILE = os.path.join(OUTPUT_DIR, "Predictions_latest_Explained.csv")

# --- helper ---
def log(msg): print(f"{dt.datetime.utcnow().isoformat()}Z  {msg}", flush=True)

def load_history():
    if os.path.exists(HISTORY_FILE):
        return pd.read_csv(HISTORY_FILE)
    return pd.DataFrame(columns=["Date","Sport","Game","BetType","Pick","Result","Edge","Confidence"])

def fetch_recent_results(sport_key):
    """pull completed games from The Odds API"""
    url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/scores/?daysFrom=3&apiKey={ODDS_API_KEY}"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code != 200: return []
        return r.json()
    except Exception as e:
        log(f"fetch_recent_results error {sport_key}: {e}")
        return []

def grade_pick(row, results):
    """mark pick as WIN/LOSS if result available"""
    for g in results:
        h, a = (g.get("home_team",""), g.get("away_team",""))
        if not g.get("completed"): continue
        if row["Team1"] in (h,a) and row["Team2"] in (h,a):
            scores = g.get("scores", [])
            if len(scores)==2:
                home, away = scores[0]["score"], scores[1]["score"]
                win = h if home>away else a
                return "WIN" if row["MoneylinePick"].startswith(win) else "LOSS"
    return np.nan

def weighted_adjustment(hist):
    """compute recent accuracy weight by sport"""
    if hist.empty: return {}
    adj = {}
    recent = hist[hist["Result"].isin(["WIN","LOSS"])].tail(200)
    for s, g in recent.groupby("Sport"):
        wins = (g["Result"]=="WIN").sum()
        tot = len(g)
        adj[s] = round(wins/tot,3) if tot>0 else 1.0
    return adj

# --- main ---
def main():
    log("🧠 LockBox Learning cycle start")

    # load latest predictions
    if not os.path.exists(PRED_FILE):
        log("no predictions file found")
        return
    df = pd.read_csv(PRED_FILE)
    if df.empty:
        log("no rows in predictions")
        return

    hist = load_history()
    all_results = {
        "americanfootball_nfl": fetch_recent_results("americanfootball_nfl"),
        "americanfootball_ncaaf": fetch_recent_results("americanfootball_ncaaf"),
        "basketball_nba": fetch_recent_results("basketball_nba"),
        "icehockey_nhl": fetch_recent_results("icehockey_nhl"),
        "baseball_mlb": fetch_recent_results("baseball_mlb"),
    }

    graded_rows = []
    for _, r in df.iterrows():
        res = grade_pick(r, all_results.get(r.get("Sport_raw",""), []))
        if isinstance(res,str):
            graded_rows.append({
                "Date": dt.datetime.utcnow().date(),
                "Sport": r.get("Sport",""),
                "Game": f"{r.get('Team1')} vs {r.get('Team2')}",
                "BetType": "ATS",
                "Pick": r.get("MoneylinePick",""),
                "Result": res,
                "Edge": r.get("Edge",0),
                "Confidence": r.get("Confidence",0)
            })

    if graded_rows:
        new = pd.DataFrame(graded_rows)
        hist = pd.concat([hist,new], ignore_index=True)
        hist.to_csv(HISTORY_FILE,index=False)
        log(f"✅ Appended {len(new)} results to history")
    else:
        log("No new graded results")

    # adjust scaling weights
    adj = weighted_adjustment(hist)
    log(f"Performance weights: {adj}")

    # apply slight learning bias
    if adj:
        for i, r in df.iterrows():
            sport = r.get("Sport","")
            if sport in adj:
                w = adj[sport]
                df.at[i,"Edge"] = r["Edge"] * (0.9 + 0.2*w)
                df.at[i,"Confidence"] = min(100, r["Confidence"] * (0.9 + 0.2*w))

    # save adjusted predictions
    date_str = dt.datetime.utcnow().strftime("%Y-%m-%d")
    out_path = os.path.join(OUTPUT_DIR, f"Predictions_{date_str}_Explained.csv")
    df.to_csv(out_path, index=False)
    df.to_csv(PRED_FILE, index=False)
    log(f"✅ Updated {PRED_FILE} with {len(df)} rows")
    log("🚀 Learning cycle complete")

if __name__ == "__main__":
    main()
