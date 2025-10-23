#!/usr/bin/env python3
"""
backfill_history.py — LockBox Pro Historical Builder

Pulls completed game results day-by-day (past 1-day window) from The Odds API
and appends them into Output/history.csv.

This works even on free plans that only support daysFrom=1 by looping backward.
"""

import os, time, requests, pandas as pd
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Config
ROOT = Path(".")
OUT_DIR = ROOT / "Output"
OUT_DIR.mkdir(exist_ok=True)
HISTORY_FILE = OUT_DIR / "history.csv"

API_KEY = os.getenv("ODDS_API_KEY")
BASE_URL = "https://api.the-odds-api.com/v4/sports/{sport}/scores"

SPORTS = {
    "NFL": "americanfootball_nfl",
    "NCAAF": "americanfootball_ncaaf",
    "NBA": "basketball_nba",
    "NHL": "icehockey_nhl",
    "MLB": "baseball_mlb",
}

START_DATE = datetime(2025, 8, 1, tzinfo=timezone.utc)  # season start
TODAY = datetime.now(timezone.utc)

# Load or create history.csv
if HISTORY_FILE.exists():
    existing = pd.read_csv(HISTORY_FILE)
else:
    existing = pd.DataFrame(columns=["Date", "Sport", "Home", "Away", "HomeScore", "AwayScore", "Winner"])

def fetch_scores(sport_key: str):
    """Fetch results for the last 1 day (API limited)."""
    url = BASE_URL.format(sport=sport_key)
    try:
        r = requests.get(url, params={"apiKey": API_KEY, "daysFrom": 1}, timeout=10)
        if r.status_code != 200:
            print(f"⚠️ {sport_key}: API error {r.status_code}")
            return []
        return r.json()
    except Exception as e:
        print(f"⚠️ {sport_key}: {e}")
        return []

def normalize_team(name):
    return str(name or "").strip().lower()

def add_results_for_day(day: datetime):
    global existing
    print(f"\n📅 Fetching games around {day.date()}...")
    added = 0
    for sport, api_sport in SPORTS.items():
        data = fetch_scores(api_sport)
        for g in data:
            if not g.get("completed"):
                continue
            date = g.get("commence_time", "")[:10]
            home = g.get("home_team")
            away = g.get("away_team")
            scores = g.get("scores", [])
            if not scores or len(scores) != 2:
                continue

            try:
                sh = next(float(s["score"]) for s in scores if normalize_team(s["name"]) == normalize_team(home))
                sa = next(float(s["score"]) for s in scores if normalize_team(s["name"]) == normalize_team(away))
            except Exception:
                continue

            winner = home if sh > sa else away
            if not existing.empty and ((existing["Date"] == date) & (existing["Home"] == home) & (existing["Away"] == away)).any():
                continue

            existing.loc[len(existing)] = [date, sport, home, away, sh, sa, winner]
            added += 1
    if added:
        existing.to_csv(HISTORY_FILE, index=False)
        print(f"✅ Added {added} new results to history.csv")
    else:
        print("ℹ️ No new results today.")

def main():
    days = (TODAY - START_DATE).days
    print(f"🕒 Backfilling roughly {days} days of results...")
    for i in range(days):
        day = TODAY - timedelta(days=i)
        add_results_for_day(day)
        time.sleep(1.5)  # API courtesy delay
    print(f"\n🏁 Done! {len(existing)} total games saved → {HISTORY_FILE}")

if __name__ == "__main__":
    main()
