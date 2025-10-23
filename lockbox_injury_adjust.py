#!/usr/bin/env python3
# lockbox_injury_adjust.py — integrates NFL DFS injury/availability info via RapidAPI (Tank01 endpoint)

import os, json, pandas as pd, requests
from pathlib import Path
from datetime import datetime

ROOT = Path(".")
OUT_DIR = ROOT / "Output"
LATEST_FILE = OUT_DIR / "Predictions_latest_Explained.csv"
OUT_ADJ = OUT_DIR / "Predictions_latest_InjuryAdjusted.csv"

RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")
API_URL = "https://tank01-nfl-live-in-game-real-time-statistics-nfl.p.rapidapi.com/getNFLDFS"

HEADERS = {
    "x-rapidapi-host": "tank01-nfl-live-in-game-real-time-statistics-nfl.p.rapidapi.com",
    "x-rapidapi-key": RAPIDAPI_KEY or ""
}

def fetch_dfs_injuries():
    """Fetch DFS player data (includes injury info)"""
    today = datetime.utcnow().strftime("%Y%m%d")
    try:
        params = {"date": today, "includeTeamDefense": "true"}
        r = requests.get(API_URL, headers=HEADERS, params=params, timeout=25)
        if r.status_code != 200:
            print(f"⚠️ DFS API error {r.status_code} → {API_URL}")
            return []
        data = r.json()
        players = data.get("body") or []
        injured = []
        for p in players:
            stat = (p.get("injuryStatus") or "").strip()
            if stat and stat.lower() not in ("active", "none", "healthy"):
                injured.append({
                    "player": p.get("playerName", ""),
                    "team": p.get("teamAbv", ""),
                    "pos": p.get("pos", ""),
                    "status": stat,
                    "salary": p.get("salary", "")
                })
        print(f"📋 Retrieved {len(injured)} injured/questionable players.")
        return injured
    except Exception as e:
        print("⚠️ Injury fetch failed:", e)
        return []

def normalize_team(name):
    if not isinstance(name, str): return ""
    return name.strip().upper()[:3]

def apply_injury_adjustments(df, injuries):
    """Reduce confidence if team has notable injuries"""
    if not injuries:
        print("⚠️ No injury data — skipping adjustment.")
        df.to_csv(OUT_ADJ, index=False)
        return df, 0

    inj_df = pd.DataFrame(injuries)
    inj_df["team"] = inj_df["team"].astype(str).apply(normalize_team)
    adj_count = 0

    # Weighted penalties by position
    weights = {"QB": 15, "RB": 10, "WR": 8, "TE": 8, "CB": 6, "LB": 6, "S": 5, "DL": 5}
    team_penalty = {}
    for _, r in inj_df.iterrows():
        team = r["team"]
        pos = r.get("pos", "")
        penalty = weights.get(pos, 4)
        team_penalty[team] = team_penalty.get(team, 0) + penalty

    for i, row in df.iterrows():
        pick = str(row.get("BestPick", ""))
        conf = float(row.get("Confidence", 0))
        for t, pen in team_penalty.items():
            if t in pick:
                df.at[i, "Confidence"] = max(0, conf - pen)
                df.at[i, "Reason"] += f" | Injury adj -{pen} ({t})"
                adj_count += 1
                break

    df.to_csv(OUT_ADJ, index=False)
    print(f"✅ Injury-adjusted file saved: {OUT_ADJ}")
    print(f"🧩 Adjusted {adj_count} picks based on DFS injury data")
    return df, adj_count

def main():
    if not LATEST_FILE.exists():
        print("❌ No predictions file found.")
        return
    df = pd.read_csv(LATEST_FILE)
    print(f"📘 Loaded {len(df)} predictions")

    injuries = fetch_dfs_injuries()
    apply_injury_adjustments(df, injuries)

if __name__ == "__main__":
    main()
