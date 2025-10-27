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
def log(msg):
    print(f"{dt.datetime.utcnow().isoformat()}Z  {msg}", flush=True)

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            df = pd.read_csv(HISTORY_FILE)
            if "Result" not in df.columns:
                df["Result"] = ""
            return df
        except Exception as e:
            log(f"⚠️ Error reading history: {e}")
    return pd.DataFrame(columns=["Date","Sport","Game","BetType","Pick","Result","Edge","Confidence"])

def fetch_recent_results(sport_key):
    """Pull completed games from The Odds API"""
    url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/scores/?daysFrom=3&apiKey={ODDS_API_KEY}"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code != 200:
            log(f"⚠️ Bad response for {sport_key}: {r.status_code}")
            return []
        return r.json()
    except Exception as e:
        log(f"fetch_recent_results error {sport_key}: {e}")
        return []

def grade_pick(row, results):
    """Mark pick as WIN/LOSS if result available"""
    for g in results:
        h, a = (g.get("home_team",""), g.get("away_team",""))
        if not g.get("completed"):
            continue
        if row["Team1"] in (h,a) and row["Team2"] in (h,a):
            scores = g.get("scores", [])
            if len(scores)==2:
                home, away = scores[0]["score"], scores[1]["score"]
                win = h if home>away else a
                return "WIN" if row["MoneylinePick"].startswith(win) else "LOSS"
    return np.nan

def weighted_adjustment(hist):
    """Adjust learning weights safely — skip if no results yet."""
    if hist is None or hist.empty:
        print("⚠️ No history data available — skipping weighted adjustment.")
        return {}

    if "Result" not in hist.columns:
        print("⚠️ No 'Result' column found — first run detected, skipping adjustment.")
        return {}

    recent = hist[hist["Result"].isin(["WIN", "LOSS"])].tail(200)
    if recent.empty:
        print("⚠️ No graded results yet — skipping adjustment.")
        return {}

    try:
        sport_perf = recent.groupby("Sport")["Result"].apply(lambda x: (x == "WIN").mean())
        weights = sport_perf.to_dict()
        print("🧠 Adaptive sport performance:", weights)
        return weights
    except Exception as e:
        print(f"⚠️ Weighted adjustment skipped due to error: {e}")
        return {}

# --- main ---
def main():
    log("🧠 LockBox Learning cycle start")

    # Load latest predictions
    if not os.path.exists(PRED_FILE):
        log("❌ No predictions file found.")
        return
    df = pd.read_csv(PRED_FILE)
    if df.empty:
        log("❌ No rows in predictions.")
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
        if isinstance(res, str):
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
        hist = pd.concat([hist, new], ignore_index=True)
        hist.to_csv(HISTORY_FILE, index=False)
        log(f"✅ Appended {len(new)} results to history")
    else:
        log("ℹ️ No new graded results (first cycle likely)")

    # Adjust scaling weights
    adj = weighted_adjustment(hist)
    log(f"Performance weights: {adj}")

    # Apply slight learning bias if available
    if adj:
        for i, r in df.iterrows():
            sport = r.get("Sport","")
            if sport in adj:
                w = adj[sport]
                df.at[i,"Edge"] = r["Edge"] * (0.9 + 0.2*w)
                df.at[i,"Confidence"] = min(100, r["Confidence"] * (0.9 + 0.2*w))

    # Save adjusted predictions
    date_str = dt.datetime.utcnow().strftime("%Y-%m-%d")
    out_path = os.path.join(OUTPUT_DIR, f"Predictions_{date_str}_Explained.csv")
    df.to_csv(out_path, index=False)
    df.to_csv(PRED_FILE, index=False)
    log(f"✅ Updated {PRED_FILE} with {len(df)} rows")
    log("🚀 Learning cycle complete")

if __name__ == "__main__":
    main()
