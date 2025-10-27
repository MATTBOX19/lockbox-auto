#!/usr/bin/env python3
"""
LockBox — API-Sports Odds Fetcher (Direct, not RapidAPI)
Pulls odds for major US leagues and saves raw JSON snapshots into /Output.

Usage (local or Render shell):
  python fetch_apisports_live.py

Env vars used:
  - API_SPORTS_KEY  (preferred) or APISPORTS_KEY
  - OUTPUT_DIR      (default: /opt/render/project/src/Output)
  - APISPORTS_BOOKMAKER_ID (optional, default: 8)
"""

import os
import json
import time
import datetime as dt
import requests

# --- Config / Env ---
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "/opt/render/project/src/Output")
API_KEY = os.getenv("API_SPORTS_KEY") or os.getenv("APISPORTS_KEY")
BOOKMAKER_ID = int(os.getenv("APISPORTS_BOOKMAKER_ID", "8"))  # keep 8 unless you prefer another
os.makedirs(OUTPUT_DIR, exist_ok=True)

# API-Sports (direct) hosts per sport
SPORT_ENDPOINTS = {
    "americanfootball_nfl":   "https://v1.american-football.api-sports.io/odds",
    "americanfootball_ncaaf": "https://v1.american-football.api-sports.io/odds",
    "basketball_nba":         "https://v1.basketball.api-sports.io/odds",
    "baseball_mlb":           "https://v1.baseball.api-sports.io/odds",
    "icehockey_nhl":          "https://v1.hockey.api-sports.io/odds",
}

HEADERS = {"x-apisports-key": API_KEY} if API_KEY else {}

def log(msg: str) -> None:
    print(f"{dt.datetime.utcnow().isoformat()}Z  {msg}", flush=True)

def fetch_odds_for_sport(sport_key: str) -> list:
    """Fetch odds for a given sport; returns API 'response' list (or [])."""
    if not API_KEY:
        log("❌ Missing API_SPORTS_KEY/APISPORTS_KEY in environment.")
        return []

    url = SPORT_ENDPOINTS.get(sport_key)
    if not url:
        log(f"❌ Unknown sport key: {sport_key}")
        return []

    try:
        params = {"bookmaker": BOOKMAKER_ID}
        r = requests.get(url, headers=HEADERS, params=params, timeout=25)
        if r.status_code != 200:
            log(f"⚠️ {sport_key} bad response: {r.status_code} — {r.text[:180]}")
            return []
        payload = r.json() or {}
        resp = payload.get("response", [])
        log(f"📊 {sport_key}: results={payload.get('results', len(resp))}")
        return resp
    except Exception as e:
        log(f"⚠️ {sport_key} fetch error: {e}")
        return []

def save_json(sport_key: str, data: list) -> None:
    """Save raw odds JSON snapshot into Output with date stamp."""
    date = dt.datetime.utcnow().strftime("%Y-%m-%d")
    path = os.path.join(OUTPUT_DIR, f"{sport_key}_odds_{date}.json")
    try:
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        log(f"✅ Saved {len(data)} odds → {path}")
    except Exception as e:
        log(f"⚠️ Save error for {sport_key}: {e}")

def main():
    log("🚀 Fetching live odds from API-Sports (direct)")
    if not API_KEY:
        log("❌ No API key found — set API_SPORTS_KEY or APISPORTS_KEY")
        return

    for sport in SPORT_ENDPOINTS.keys():
        data = fetch_odds_for_sport(sport)
        if data:
            save_json(sport, data)
        time.sleep(1.5)  # gentle pacing
    log("✅ All odds fetched")

if __name__ == "__main__":
    main()
