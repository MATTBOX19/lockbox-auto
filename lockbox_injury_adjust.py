#!/usr/bin/env python3
# lockbox_injury_adjust.py — uses Tank01 public injury endpoint via RapidAPI

import os, json, pandas as pd, requests
from pathlib import Path

ROOT = Path(".")
OUT_DIR = ROOT / "Output"
LATEST_FILE = OUT_DIR / "Predictions_latest_Explained.csv"
OUT_ADJ = OUT_DIR / "Predictions_latest_InjuryAdjusted.csv"

RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")
API_URL = "https://tank01-nfl-live-in-game-real-time-statistics-nfl.p.rapidapi.com/getNFLInjuriesV2"
HEADERS = {
    "x-rapidapi-host": "tank01-nfl-live-in-game-real-time-statistics-nfl.p.rapidapi.com",
    "x-rapidapi-key": RAPIDAPI_KEY or ""
}

def fetch_injuries():
    """Fetch injury report from RapidAPI Tank01 feed (V2 free endpoint)"""
    try:
        params = {"season": "2025", "week": "7"}
        r = requests.get(API_URL, headers=HEADERS, params=params, timeout=25)
        if r.status_code != 200:
            print(f"⚠️ Injury API error {r.status_code} → {API_URL}")
            print("Response:", r.text[:200])
            return []
        data = r.json()
        injuries = data.get("body") or data.get("response") or []
        print(f"📋 Retrieved {len(injuries)} injury entries.")
        return injuries
    except Exception as e:
        print("⚠️ Injury fetch failed:", e)
        return []

def normalize_team(name):
    """Map team abbreviations"""
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
    """Reduce confidence if key players are out"""
    if not injuries:
        print("⚠️ No injury data — skipping adjustment.")
        df.to_csv(OUT_ADJ, index=False)
        return df, 0

    inj_df = pd.DataFrame(injuries)
    inj_df["team"] = inj_df.get("teamAbv", inj_df.get("team", "")).astype(str).apply(normalize_team)
    inj_df["status"] = inj_df.get("injuryStatus", inj_df.get("status", "")).astype(str)
    inj_df["player"] = inj_df.get("player", inj_df.get("playerName", "")).astype(str)
    inj_df = inj_df[inj_df["status"].str.contains("Out|Questionable|Doubtful", case=False, na=False)]

    team_injury_counts = inj_df.groupby
