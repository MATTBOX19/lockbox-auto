#!/usr/bin/env python3
"""
LockBox — Build Predictions CSV from API-Sports odds (direct API, not RapidAPI)

- Reads live odds directly from API-Sports endpoints (no snapshot required)
- Creates Output/Predictions_latest_Explained.csv in the SAME schema your web uses
- Also writes a dated copy: Output/Predictions_YYYY-MM-DD_Explained.csv

Env:
  API_SPORTS_KEY  (or APISPORTS_KEY)
  OUTPUT_DIR=/opt/render/project/src/Output (default)
  APISPORTS_BOOKMAKER_ID=8 (default; 8 = Bet365 in API-Sports)
"""

import os, math, json, time
import datetime as dt
import requests
import pandas as pd

OUTPUT_DIR = os.getenv("OUTPUT_DIR", "/opt/render/project/src/Output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

API_KEY = os.getenv("API_SPORTS_KEY") or os.getenv("APISPORTS_KEY")
BOOKMAKER_ID = int(os.getenv("APISPORTS_BOOKMAKER_ID", "8"))  # 8 = Bet365 per API-Sports docs

HEADERS = {"x-apisports-key": API_KEY} if API_KEY else {}

SPORT_ENDPOINTS = {
    "americanfootball_nfl":   "https://v1.american-football.api-sports.io/odds",
    "americanfootball_ncaaf": "https://v1.american-football.api-sports.io/odds",
    "basketball_nba":         "https://v1.basketball.api-sports.io/odds",
    "baseball_mlb":           "https://v1.baseball.api-sports.io/odds",
    "icehockey_nhl":          "https://v1.hockey.api-sports.io/odds",
}

SPORT_PRETTY = {
    "americanfootball_nfl": "NFL",
    "americanfootball_ncaaf": "CFB",
    "basketball_nba": "NBA",
    "baseball_mlb": "MLB",
    "icehockey_nhl": "NHL",
}

def log(s): print(f"{dt.datetime.utcnow().isoformat()}Z  {s}", flush=True)

def amer_to_prob(odds_str: str) -> float | None:
    """American odds -> implied prob (0-1). Return None if parse fails."""
    try:
        o = float(odds_str)
        if o > 0:
            return 100.0 / (o + 100.0)
        else:
            return (-o) / ((-o) + 100.0)
    except:
        return None

def best_ml_from_bets(bets: list) -> tuple[float|None, float|None]:
    """
    From API-Sports 'bets' array, find moneyline (Home/Away) odds as American odds.
    Returns tuple (home_odds, away_odds) as floats when possible; otherwise None.
    """
    if not isinstance(bets, list):
        return (None, None)
    # API-Sports ML names vary a bit by sport; handle common variants
    ML_NAMES = {"Home/Away", "Match Winner", "Moneyline"}
    for b in bets:
        name = str(b.get("name", "")).strip()
        if name not in ML_NAMES:
            continue
        values = b.get("values", [])
        home, away = None, None
        for v in values:
            val_name = str(v.get("value", "")).lower()
            odd_str = str(v.get("odd", "")).strip()
            # Some books give decimal odds; API-Sports often returns as decimal. Convert decimal->American if needed.
            # Heuristic: decimal odds usually contain '.', and > 1.01; American odds are typically ints.
            try:
                if "." in odd_str:
                    dec = float(odd_str)
                    # decimal -> American
                    if dec >= 2.0:
                        american = (dec - 1.0) * 100.0
                    else:
                        american = -100.0 / (dec - 1.0)
                    odd_num = round(american)
                else:
                    odd_num = float(odd_str)
            except:
                odd_num = None

            if "home" in val_name:
                home = odd_num
            elif "away" in val_name:
                away = odd_num
        return (home, away)
    return (None, None)

def fetch_odds(sport_key: str) -> list:
    url = SPORT_ENDPOINTS[sport_key]
    params = {"bookmaker": BOOKMAKER_ID}
    r = requests.get(url, headers=HEADERS, params=params, timeout=25)
    if r.status_code != 200:
        log(f"⚠️ {sport_key} HTTP {r.status_code}: {r.text[:200]}")
        return []
    payload = r.json() or {}
    resp = payload.get("response", [])
    log(f"📊 {sport_key}: {payload.get('results', len(resp))} events")
    return resp

def choose_pick(team_home: str, team_away: str, home_ml: float|None, away_ml: float|None):
    """
    Decide ML pick from odds. Return (pick_text, conf_pct, edge, ml_display).
    conf% is crude implied prob * 100; edge is (fav_prob - 0.5) bounded at 0 if negative.
    """
    # Build ML display string
    ml_display = f"{team_home}:{int(home_ml) if home_ml is not None else '?'} | {team_away}:{int(away_ml) if away_ml is not None else '?'}"

    # If no odds, abstain
    if home_ml is None and away_ml is None:
        return ("No Pick", 50.0, 0.0, ml_display)

    p_home = amer_to_prob(home_ml) if home_ml is not None else None
    p_away = amer_to_prob(away_ml) if away_ml is not None else None

    # determine favorite
    # (lower implied payout -> higher probability)
    if p_home is None and p_away is None:
        return ("No Pick", 50.0, 0.0, ml_display)
    if (p_home or 0) >= (p_away or 0):
        fav_team, fav_prob = team_home, (p_home or 0.5)
    else:
        fav_team, fav_prob = team_away, (p_away or 0.5)

    confidence_pct = round(100.0 * fav_prob, 1)
    edge = round(max(0.0, fav_prob - 0.5), 3)
    pick_text = f"{fav_team} ML"

    return (pick_text, confidence_pct, edge, ml_display)

def normalize_event(sport_key: str, ev: dict) -> dict | None:
    """
    Convert one API-Sports odds event to LockBox row expected by the web:
    Required output columns:
      Sport, Sport_raw, GameTime, Team1, Team2, MoneylinePick, Confidence, Edge,
      ML, ATS, OU, Reason, LockEmoji, UpsetEmoji, EdgeDisplay
    """
    try:
        league = ev.get("league", {})
        game   = ev.get("game", {}) or ev.get("fixture", {})  # some sports use 'fixture'
        update = ev.get("update", "")
        country = ev.get("country", {})
        bookmakers = ev.get("bookmakers", [])

        # teams: API often nests under ev["teams"]{"home":{"name":..},"away":{"name":..}}
        teams = ev.get("teams", {})
        team_home = teams.get("home", {}).get("name") or game.get("home", "")
        team_away = teams.get("away", {}).get("name") or game.get("away", "")

        # fallback
        if not team_home or not team_away:
            # some payloads put names in game dict as 'home'/'away' or 'home_name'/'away_name'
            team_home = game.get("home_name") or game.get("home") or team_home or "Home"
            team_away = game.get("away_name") or game.get("away") or team_away or "Away"

        # get ML odds from chosen bookmaker
        home_ml, away_ml = None, None
        for bk in bookmakers:
            if int(bk.get("id", -1)) == BOOKMAKER_ID:
                home_ml, away_ml = best_ml_from_bets(bk.get("bets", []))
                break

        pick, conf_pct, edge, ml_display = choose_pick(team_home, team_away, home_ml, away_ml)

        # simple text reason
        reason = f"Selected by implied probability from bookmaker {BOOKMAKER_ID}. Source: API-Sports."

        row = {
            "Sport_raw": sport_key,
            "Sport": SPORT_PRETTY.get(sport_key, sport_key.upper()),
            "GameTime": update or "",
            "Team1": team_home,
            "Team2": team_away,
            "MoneylinePick": pick,
            "Confidence": conf_pct,
            "Edge": edge,
            "EdgeDisplay": f"{edge:.3f}",
            "ML": ml_display,
            "ATS": "-",   # can populate spreads after phase 2
            "OU": "-",    # can populate totals after phase 2
            "Reason": reason,
            "LockEmoji": "🔒" if (edge >= 0.15 and conf_pct >= 60) else "",
            "UpsetEmoji": "🚨" if (edge < 0.05 and conf_pct < 55) else "",
        }
        return row
    except Exception as e:
        log(f"⚠️ normalize error: {e}")
        return None

def main():
    if not API_KEY:
        log("❌ Missing API_SPORTS_KEY/APISPORTS_KEY.")
        return

    all_rows = []
    for sport_key, url in SPORT_ENDPOINTS.items():
        try:
            r = requests.get(url, headers=HEADERS, params={"bookmaker": BOOKMAKER_ID}, timeout=25)
            if r.status_code != 200:
                log(f"⚠️ {sport_key} HTTP {r.status_code}: {r.text[:160]}")
                continue
            payload = r.json() or {}
            resp = payload.get("response", [])
            log(f"📊 {sport_key}: {payload.get('results', len(resp))} events")
            for ev in resp:
                row = normalize_event(sport_key, ev)
                if row:
                    all_rows.append(row)
            time.sleep(1.0)
        except Exception as e:
            log(f"⚠️ fetch error {sport_key}: {e}")

    if not all_rows:
        log("ℹ️ No events parsed — nothing to write.")
        return

    df = pd.DataFrame(all_rows)

    # sort by (Edge * Confidence) like your Top5
    df["Score"] = df["Edge"].astype(float) * df["Confidence"].astype(float)
    df = df.sort_values("Score", ascending=False)

    date_str = dt.datetime.utcnow().strftime("%Y-%m-%d")
    latest = os.path.join(OUTPUT_DIR, "Predictions_latest_Explained.csv")
    dated  = os.path.join(OUTPUT_DIR, f"Predictions_{date_str}_Explained.csv")

    # Drop helper col and write
    out = df.drop(columns=["Score"])
    out.to_csv(latest, index=False)
    out.to_csv(dated,  index=False)

    log(f"✅ Wrote {len(out)} rows → {latest}")
    log(f"✅ Wrote {len(out)} rows → {dated}")
    log("🚀 Done — CSV ready for web.")
    
if __name__ == "__main__":
    main()
