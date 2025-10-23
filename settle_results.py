#!/usr/bin/env python3
"""
settle_results.py — LockBox Pro

Fetches final scores from The Odds API and grades:
 - Moneyline (ML)
 - Against The Spread (ATS)
 - Over/Under (OU)

Outputs:
  Output/Predictions_<date>_Settled.csv
  Appends each graded bet (ML/ATS/OU) to Output/history.csv
"""

import os, requests, pandas as pd
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(".")
OUT_DIR = ROOT / "Output"
LATEST_FILE = OUT_DIR / "Predictions_latest_Explained.csv"
SETTLED_FILE = OUT_DIR / f"Predictions_{datetime.now(timezone.utc).strftime('%Y-%m-%d')}_Settled.csv"
HISTORY_FILE = OUT_DIR / "history.csv"

API_KEY = os.getenv("ODDS_API_KEY")
RESULTS_URL = "https://api.the-odds-api.com/v4/sports/{sport}/scores"

SPORT_MAP = {
    "NFL": "americanfootball_nfl",
    "NCAAF": "americanfootball_ncaaf",
    "NBA": "basketball_nba",
    "NHL": "icehockey_nhl",
    "MLB": "baseball_mlb",
}

def fetch_results(api_sport):
    url = RESULTS_URL.format(sport=api_sport)
    try:
        r = requests.get(url, params={"apiKey": API_KEY, "daysFrom": 3}, timeout=15)
        if r.status_code != 200:
            print(f"⚠️ API error {r.status_code} for {api_sport}")
            return []
        data = r.json()
        print(f"📊 Retrieved {len(data)} results for {api_sport}")
        return data
    except Exception as e:
        print(f"⚠️ Fetch error for {api_sport}: {e}")
        return []

def normalize_team_name(name: str):
    return str(name or "").lower().replace(".", "").replace("-", " ").replace("state", "st").strip()

def parse_spread_points(ats_field: str, team: str):
    try:
        if not isinstance(ats_field, str) or "|" not in ats_field:
            return None
        parts = ats_field.split("|")
        for p in parts:
            name, val = p.split(":")
            if team.lower() in name.lower():
                return float(val)
    except Exception:
        pass
    return None

def parse_total_points(ou_field: str):
    try:
        if not isinstance(ou_field, str) or "Over:" not in ou_field:
            return None
        val = ou_field.split("Over:")[1].split("/")[0]
        return float(val)
    except Exception:
        return None

def determine_results(row, sport_results):
    team_pick = str(row.get("BestPick", "")).split("(")[0].strip()
    team_norm = normalize_team_name(team_pick)
    ats_line = row.get("ATS", "")
    ou_line = row.get("OU", "")
    ml_res = ats_res = ou_res = None

    for g in sport_results:
        home = normalize_team_name(g.get("home_team"))
        away = normalize_team_name(g.get("away_team"))
        if team_norm not in [home, away]:
            continue
        scores = g.get("scores", [])
        if not scores or len(scores) != 2:
            continue

        sh = next((float(s["score"]) for s in scores if normalize_team_name(s["name"]) == home), None)
        sa = next((float(s["score"]) for s in scores if normalize_team_name(s["name"]) == away), None)
        if sh is None or sa is None:
            continue

        # ML
        winner = home if sh > sa else away
        ml_res = "Win" if team_norm == winner else "Loss"

        # ATS
        spread = parse_spread_points(ats_line, team_pick)
        if spread is not None:
            margin = sh - sa if home == team_norm else sa - sh
            ats_res = "Win" if margin + spread > 0 else "Loss"

        # OU
        total_line = parse_total_points(ou_line)
        if total_line is not None:
            total = sh + sa
            if "Over" in ou_line and total > total_line:
                ou_res = "Win"
            elif "Under" in ou_line and total < total_line:
                ou_res = "Win"
            else:
                ou_res = "Loss"
        break

    return ml_res, ats_res, ou_res

def main():
    if not LATEST_FILE.exists():
        print("❌ No latest predictions file found.")
        return

    df = pd.read_csv(LATEST_FILE)
    df.columns = [c.strip() for c in df.columns]
    df["ML_Result"], df["ATS_Result"], df["OU_Result"], df["Settled"] = "", "", "", False

    all_rows = []
    for sport, api_sport in SPORT_MAP.items():
        results = fetch_results(api_sport)
        mask = df["Sport"].astype(str).str.upper() == sport
        for idx in df[mask].index:
            ml, ats, ou = determine_results(df.loc[idx], results)
            if ml or ats or ou:
                df.at[idx, "Settled"] = True
            if ml: df.at[idx, "ML_Result"] = ml
            if ats: df.at[idx, "ATS_Result"] = ats
            if ou: df.at[idx, "OU_Result"] = ou

            # Log to history
            game = f"{df.at[idx, 'Team1']} vs {df.at[idx, 'Team2']}"
            pick = str(df.at[idx, 'BestPick'])
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            if ml:  all_rows.append([today, game, sport, pick, "ML", ml])
            if ats: all_rows.append([today, game, sport, pick, "ATS", ats])
            if ou:  all_rows.append([today, game, sport, pick, "OU", ou])

    df.to_csv(SETTLED_FILE, index=False)
    print(f"✅ Settled file saved → {SETTLED_FILE}")

    if all_rows:
        hist_df = pd.DataFrame(all_rows, columns=["Date","Game","Sport","Pick","BetType","Result"])
        if HISTORY_FILE.exists():
            old = pd.read_csv(HISTORY_FILE)
            hist_df = pd.concat([old, hist_df], ignore_index=True)
        hist_df.to_csv(HISTORY_FILE, index=False)
        print(f"📈 Appended {len(all_rows)} graded bets to history.csv")
    else:
        print("⚠️ No settled results to log.")

if __name__ == "__main__":
    main()
