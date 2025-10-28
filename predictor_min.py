#!/usr/bin/env python3
"""
LockBox Pro – Learning Predictor (API-Sports Edition)
Grades past picks and adjusts edge/confidence by sport performance.
"""

import os, pandas as pd, requests, datetime as dt, numpy as np, json

OUTPUT_DIR = os.getenv("OUTPUT_DIR", "/opt/render/project/src/Output")
API_SPORTS_KEY = os.getenv("API_SPORTS_KEY", "")
os.makedirs(OUTPUT_DIR, exist_ok=True)

HISTORY_FILE = os.path.join(OUTPUT_DIR, "history.csv")
PRED_FILE = os.path.join(OUTPUT_DIR, "Predictions_latest_Explained.csv")

# -------------------------------
# Helper
# -------------------------------
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

# -------------------------------
# API-Sports utilities
# -------------------------------
SPORT_MAP = {
    "americanfootball_nfl": ("american-football", 1, "2025"),
    "americanfootball_ncaaf": ("american-football", 2, "2025"),
    "basketball_nba": ("basketball", 12, "2025-2026"),
    "icehockey_nhl": ("hockey", 57, "2025"),
    "baseball_mlb": ("baseball", 1, "2025"),
}

def fetch_recent_results(sport_key):
    """Pull completed games from API-Sports"""
    if sport_key not in SPORT_MAP:
        return []
    api_group, league_id, season = SPORT_MAP[sport_key]
    url = f"https://v1.{api_group}.api-sports.io/games"
    params = {
        "league": league_id,
        "season": season,
        "to": dt.datetime.utcnow().strftime("%Y-%m-%d"),
        "from": (dt.datetime.utcnow() - dt.timedelta(days=3)).strftime("%Y-%m-%d"),
    }
    try:
        r = requests.get(url, headers={"x-apisports-key": API_SPORTS_KEY}, params=params, timeout=15)
        if r.status_code != 200:
            log(f"⚠️ Bad response for {sport_key}: {r.status_code}")
            return []
        data = r.json().get("response", [])
        completed = [g for g in data if g.get("status", {}).get("short") in ("FT","AOT","ENDED","FT_OT","FINISHED")]
        return completed
    except Exception as e:
        log(f"fetch_recent_results error {sport_key}: {e}")
        return []

def grade_pick(row, results):
    """Mark pick as WIN/LOSS if result available"""
    for g in results:
        home = g.get("teams", {}).get("home", {}).get("name", "")
        away = g.get("teams", {}).get("away", {}).get("name", "")
        scores = g.get("scores", {})
        if not home or not away:
            continue
        if row.get("Team1") in (home, away) and row.get("Team2") in (home, away):
            try:
                home_score = scores.get("home", 0)
                away_score = scores.get("away", 0)
                winner = home if home_score > away_score else away
                pick_team = str(row.get("MoneylinePick","")).split()[0]
                return "WIN" if winner in pick_team else "LOSS"
            except Exception:
                continue
    return np.nan

# -------------------------------
# Adaptive weighting
# -------------------------------
def weighted_adjustment(hist):
    if hist is None or hist.empty:
        print("⚠️ No history data available — skipping weighted adjustment.")
        return {}

    if "Result" not in hist.columns:
        print("⚠️ No 'Result' column found — first run detected, skipping adjustment.")
        return {}

    recent = hist[hist["Result"].isin(["WIN","LOSS"])].tail(200)
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

# -------------------------------
# Main
# -------------------------------
def main():
    log("🧠 LockBox Learning cycle start")

    # Load predictions
    if not os.path.exists(PRED_FILE):
        log("❌ No predictions file found.")
        return
    df = pd.read_csv(PRED_FILE)
    if df.empty:
        log("❌ No rows in predictions.")
        return

    hist = load_history()
    all_results = {s: fetch_recent_results(s) for s in SPORT_MAP.keys()}

    graded_rows = []
    for _, r in df.iterrows():
        sport_key = r.get("Sport_raw", "") or r.get("Sport", "")
        res = grade_pick(r, all_results.get(sport_key, []))
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

    adj = weighted_adjustment(hist)
    log(f"Performance weights: {adj}")

    if adj:
        for i, r in df.iterrows():
            sport = r.get("Sport","")
            if sport in adj:
                w = adj[sport]
                df.at[i,"Edge"] = r["Edge"] * (0.9 + 0.2*w)
                df.at[i,"Confidence"] = min(100, r["Confidence"] * (0.9 + 0.2*w))

    date_str = dt.datetime.utcnow().strftime("%Y-%m-%d")
    out_path = os.path.join(OUTPUT_DIR, f"Predictions_{date_str}_Explained.csv")
    df.to_csv(out_path, index=False)
    df.to_csv(PRED_FILE, index=False)
    log(f"✅ Updated {PRED_FILE} with {len(df)} rows")
    log("🚀 Learning cycle complete")

if __name__ == "__main__":
    main()
