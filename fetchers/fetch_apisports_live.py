#!/usr/bin/env python3
"""
Robust fetcher for API-Sports that:
 - Handles american-football via /standings (avoids /teams/statistics problems)
 - Tries /teams/statistics for other sports, falls back to basic team info
 - Produces per-league CSVs and a combined Data/team_stats_latest.csv
This is a full-file replacement — save/commit as-is.
"""
import os
import time
import requests
import pandas as pd
from datetime import datetime

API_KEY = os.getenv("APISPORTS_KEY")
if not API_KEY:
    raise EnvironmentError("Missing $APISPORTS_KEY environment variable. Export APISPORTS_KEY and retry.")

HEADERS = {"x-apisports-key": API_KEY}
DATA_DIR = "Data"
os.makedirs(DATA_DIR, exist_ok=True)
SEASON = int(os.getenv("SEASON", "2025"))

# league name -> (sport domain, league_id)
LEAGUES = {
    "nfl": ("american-football", 1),
    "ncaaf": ("american-football", 2),
    "nba": ("basketball", 12),
    "mlb": ("baseball", 1),
    "nhl": ("hockey", 57),
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)
SESSION.timeout = 20


def _safe_get_json(url, params=None):
    try:
        r = SESSION.get(url, params=params, timeout=20)
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        print(f"❌ Request failed: {url} params={params} -> {exc}")
        return {}


def fetch_teams(sport: str, league_id: int, season=SEASON) -> pd.DataFrame:
    """Fetch teams list for a league."""
    url = f"https://v1.{sport}.api-sports.io/teams"
    params = {"league": league_id, "season": season}
    print(f"📊 Fetching {sport.upper()} teams...")
    data = _safe_get_json(url, params)
    resp = data.get("response") or []
    # Normalize: each item may be {'team': {...}, 'venue': {...}, ...} or simply {...}
    rows = []
    for item in resp:
        if isinstance(item, dict) and "team" in item and isinstance(item["team"], dict):
            team = item["team"]
            team_row = {
                "team_id": team.get("id"),
                "team_name": team.get("name"),
                "team_nickname": team.get("name"),
                "team_city": team.get("city") or team.get("venue", {}).get("city"),
                "raw": item,
            }
        elif isinstance(item, dict):
            team_row = {
                "team_id": item.get("id"),
                "team_name": item.get("name"),
                "team_nickname": item.get("name"),
                "team_city": item.get("city"),
                "raw": item,
            }
        else:
            continue
        rows.append(team_row)
    return pd.DataFrame(rows)


def fetch_standings(sport: str, league_id: int, season=SEASON) -> dict:
    """Fetch standings for leagues that support it; return mapping team_id -> stats dict."""
    url = f"https://v1.{sport}.api-sports.io/standings"
    params = {"league": league_id, "season": season}
    print(f"📊 Fetching {sport.upper()} standings for league={league_id} season={season}...")
    data = _safe_get_json(url, params)
    resp = data.get("response") or []
    mapping = {}
    # API may return a nested structure: list of groups each with 'league' / 'standings' etc.
    for entry in resp:
        # If entry is a dict with 'team'
        if isinstance(entry, dict) and "team" in entry:
            team = entry.get("team", {})
            tid = team.get("id")
            stats = {}
            # many APIs include 'all' or 'games' or 'points' or 'goals'
            stats["wins"] = entry.get("points")  # sometimes points used, we'll try multiple fallbacks below
            # try structured keys
            all_stats = entry.get("all") or entry.get("games") or {}
            if isinstance(all_stats, dict):
                stats["games_played"] = all_stats.get("played") or all_stats.get("played_total") or all_stats.get("matches")
                stats["wins"] = all_stats.get("win") or all_stats.get("wins") or stats.get("wins")
                stats["losses"] = all_stats.get("lose") or all_stats.get("loss") or all_stats.get("losses")
            # goals/points
            goals = entry.get("goals") or entry.get("points") or {}
            if isinstance(goals, dict):
                stats["points_for"] = goals.get("for") or goals.get("for_total") or None
                stats["points_against"] = goals.get("against") or goals.get("against_total") or None
            # Some responses wrap standings as lists
            if tid:
                mapping[tid] = stats
        # other possible shape: entry contains 'league' -> 'standings' -> [[{team...}]]
        elif isinstance(entry, dict) and "league" in entry:
            league_node = entry.get("league", {})
            standings = league_node.get("standings") or []
            # standings may be a list of lists
            for groups in standings:
                if isinstance(groups, list):
                    for s in groups:
                        team = s.get("team", {})
                        tid = team.get("id")
                        stats = {}
                        all_stats = s.get("all") or {}
                        if isinstance(all_stats, dict):
                            stats["games_played"] = all_stats.get("played")
                            stats["wins"] = all_stats.get("win") or all_stats.get("wins")
                            stats["losses"] = all_stats.get("lose") or all_stats.get("losses")
                        goals = s.get("goals") or {}
                        if isinstance(goals, dict):
                            stats["points_for"] = goals.get("for")
                            stats["points_against"] = goals.get("against")
                        if tid:
                            mapping[tid] = stats
    return mapping


def fetch_team_statistics_endpoint(sport: str, league_id: int, team_id: int, season=SEASON) -> dict:
    """Try the /teams/statistics endpoint for a team; return dict or empty."""
    url = f"https://v1.{sport}.api-sports.io/teams/statistics"
    params = {"league": league_id, "season": season, "team": team_id}
    data = _safe_get_json(url, params)
    # If API says endpoint doesn't exist it may be in data.get("errors")
    if data.get("errors"):
        return {}
    resp = data.get("response")
    if not resp:
        return {}
    # ensure it's a dict
    if isinstance(resp, dict):
        # put team_id inside
        resp["team_id"] = team_id
        return resp
    # sometimes response is list
    if isinstance(resp, list) and resp:
        first = resp[0]
        if isinstance(first, dict):
            first["team_id"] = team_id
            return first
    return {}


def build_league_stats(league_key: str, sport: str, league_id: int, season=SEASON) -> pd.DataFrame:
    print(f"🏈 Processing league: {league_key.upper()} ({sport})")
    teams_df = fetch_teams(sport, league_id, season)
    if teams_df.empty:
        print(f"⚠️ {league_key.upper()}: no teams returned.")
        return pd.DataFrame()

    results = []
    # For american-football prefer /standings (avoid /teams/statistics endpoint issues)
    standings_map = {}
    if sport == "american-football":
        standings_map = fetch_standings(sport, league_id, season)

    for _, row in teams_df.iterrows():
        tid = row.get("team_id") or row.get("team", {}).get("id") if isinstance(row.get("team"), dict) else None
        # fallback: sometimes id stored in raw payload
        if not tid:
            raw = row.get("raw") or {}
            if isinstance(raw, dict):
                t = raw.get("team") or raw
                tid = t.get("id")
        # base info
        base = {
            "league": league_key.upper(),
            "sport": sport,
            "team_id": int(tid) if tid is not None else None,
            "team_name": row.get("team_name") or None,
            "team_city": row.get("team_city") or None,
        }

        stats = {}
        # Use standings_map when available
        if base["team_id"] and standings_map.get(base["team_id"]):
            stats = standings_map.get(base["team_id"], {})
        else:
            # try statistics endpoint for non-football or as fallback
            if base["team_id"]:
                stat_resp = fetch_team_statistics_endpoint(sport, league_id, base["team_id"], season)
                # stat_resp has nested dicts. We try conservative extraction
                if stat_resp:
                    # games_played
                    gp = None
                    wins = None
                    losses = None
                    pf = None
                    pa = None
                    # games -> played
                    games = stat_resp.get("games") or stat_resp.get("games_played") or {}
                    if isinstance(games, dict):
                        gp = games.get("played") or games.get("total") or gp
                        wins = games.get("wins", {}).get("total") if isinstance(games.get("wins"), dict) else games.get("wins") or wins
                        losses = games.get("loses", {}).get("total") if isinstance(games.get("loses"), dict) else games.get("loses") or losses
                    # points
                    points = stat_resp.get("points") or {}
                    if isinstance(points, dict):
                        pf = points.get("for", {}).get("total") if isinstance(points.get("for"), dict) else points.get("for") or pf
                        pa = points.get("against", {}).get("total") if isinstance(points.get("against"), dict) else points.get("against") or pa
                    # some endpoints return 'wins' at root
                    wins = wins or stat_resp.get("wins") or stat_resp.get("win")
                    losses = losses or stat_resp.get("losses") or stat_resp.get("lose")
                    stats = {
                        "games_played": gp,
                        "wins": wins,
                        "losses": losses,
                        "points_for": pf,
                        "points_against": pa,
                    }
        # merge base + stats
        merged = {**base, **(stats or {})}
        results.append(merged)
        time.sleep(0.25)  # be kind to API

    df = pd.DataFrame(results)
    out_path = os.path.join(DATA_DIR, f"{league_key}_team_stats.csv")
    df.to_csv(out_path, index=False)
    print(f"✅ Saved {league_key.upper()} stats → {out_path} ({len(df)} rows)")
    return df


def main():
    all_dfs = []
    for league_key, (sport, league_id) in LEAGUES.items():
        try:
            df = build_league_stats(league_key, sport, league_id, season=SEASON)
            if df is not None and not df.empty:
                all_dfs.append(df)
        except Exception as e:
            print(f"❌ Error processing {league_key.upper()}: {e}")

    if not all_dfs:
        print("⚠️ No leagues produced data. Exiting.")
        return

    combined = pd.concat(all_dfs, ignore_index=True, sort=False)
    out = os.path.join(DATA_DIR, "team_stats_latest.csv")
    combined.to_csv(out, index=False)
    print(f"\n🎉 Combined {len(combined)} rows across {len(all_dfs)} leagues")
    print(f"✅ Saved merged file → {out}")
    print(f"🕒 Completed at {datetime.utcnow().isoformat()}Z")


if __name__ == "__main__":
    main()
PY
