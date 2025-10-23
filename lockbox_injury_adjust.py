#!/usr/bin/env python3
# lockbox_injury_adjust.py — integrates Tank01 NFL roster-based injury adjustments via RapidAPI

import os, json, pandas as pd, requests
from pathlib import Path

ROOT = Path(".")
OUT_DIR = ROOT / "Output"
LATEST_FILE = OUT_DIR / "Predictions_latest_Explained.csv"
OUT_ADJ = OUT_DIR / "Predictions_latest_InjuryAdjusted.csv"

RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")
API_URL = "https://tank01-nfl-live-in-game-real-time-statistics-nfl.p.rapidapi.com/getNFLTeamRoster"
HEADERS = {
    "x-rapidapi-host": "tank01-nfl-live-in-game-real-time-statistics-nfl.p.rapidapi.com",
    "x-rapidapi-key": RAPIDAPI_KEY or ""
}

def fetch_injuries():
    """Fetch injury info from Tank01 team roster endpoint"""
    try:
        params = {"season": "2025"}
        r = requests.get(API_URL, headers=HEADERS, params=params, timeout=25)
        if r.status_code != 200:
            print(f"⚠️ Injury API error {r.status_code} → {API_URL}")
            return []
        data = r.json()
        teams = data.get("body", [])
        injuries = []
        for t in teams:
            team = t.get("teamAbv")
            for p in t.get("players", []):
                if p.get("injuryStatus") not in (None, "", "None"):
                    injuries.append({
                        "team": team,
                        "player": p.get("playerName"),
                        "pos": p.get("position"),
                        "status": p.get("injuryStatus"),
                        "desc": p.get("injuryDesc")
                    })
        print(f"📋 Retrieved {len(injuries)} injured players across {len(teams)} teams.")
        return injuries
    except Exception as e:
        print("⚠️ Injury fetch failed:", e)
        return []

def normalize_team(name):
    """Normalize abbreviations"""
    if not isinstance(name, str): return ""
    name = name.upper().strip()
    if len(name) == 3: return name
    for abbr, full in {
        "BUF":"BILLS","MIA":"DOLPHINS","NE":"PATRIOTS","NYJ":"JETS","BAL":"RAVENS","PIT":"STEELERS","CLE":"BROWNS","CIN":"BENGALS",
        "KC":"CHIEFS","DEN":"BRONCOS","LAC":"CHARGERS","LV":"RAIDERS","JAX":"JAGUARS","TEN":"TITANS","IND":"COLTS","HOU":"TEXANS",
        "DAL":"COWBOYS","PHI":"EAGLES","WAS":"COMMANDERS","NYG":"GIANTS","GB":"PACKERS","CHI":"BEARS","MIN":"VIKINGS","DET":"LIONS",
        "SF":"49ERS","SEA":"SEAHAWKS","LAR":"RAMS","ARI":"CARDINALS","NO":"SAINTS","ATL":"FALCONS","CAR":"PANTHERS","TB":"BUCCANEERS"
    }.items():
        if full in name: return abbr
    return name[:3]

def apply_injury_adjustments(df, injuries):
    """Adjust confidence based on key injuries"""
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

    for _, row in inj_df.iterrows():
        team = row["team"]
        pos = row.get("pos", "")
        penalty = weights.get(pos, 4)
        team_penalty[team] = team_penalty.get(team, 0) + penalty

    for i, r in df.iterrows():
        pick = str(r.get("BestPick", ""))
        conf = float(r.get("Confidence", 0))
        for t, pen in team_penalty.items():
            if t in pick:
                df.at[i, "Confidence"] = max(0, conf - pen)
                df.at[i, "Reason"] += f" | Injury adj -{pen} ({t})"
                adj_count += 1
                break

    df.to_csv(OUT_ADJ, index=False)
    print(f"✅ Injury-adjusted file saved: {OUT_ADJ}")
    print(f"🧩 Adjusted {adj_count} picks based on live roster injuries")
    return df, adj_count

def main():
    if not LATEST_FILE.exists():
        print("❌ No predictions file found.")
        return
    df = pd.read_csv(LATEST_FILE)
    print(f"📘 Loaded {len(df)} predictions")

    injuries = fetch_injuries()
    apply_injury_adjustments(df, injuries)

if __name__ == "__main__":
    main()
