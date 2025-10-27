from __future__ import annotations

import os
import time
import requests
import pandas as pd
from datetime import datetime
from typing import Any, Dict, List, Optional

API_KEY = os.getenv("APISPORTS_KEY")
if not API_KEY:
    raise EnvironmentError("Missing $APISPORTS_KEY environment variable.")

HEADERS = {"x-apisports-key": API_KEY}
DATA_DIR = "Data"
os.makedirs(DATA_DIR, exist_ok=True)
SEASON = int(os.getenv("SEASON", "2025"))

LEAGUES = {
    "nfl": ("american-football", 1),
    "ncaaf": ("american-football", 2),
    # "nba": ("basketball", 12),  # disabled: no data returned
    "mlb": ("baseball", 1),
    "nhl": ("hockey", 57),
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)


def _safe_get_json(url: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    try:
        r = SESSION.get(url, params=params, timeout=20)
        r.raise_for_status()
        return r.json() if r.content else {}
    except Exception as exc:
        print(f"❌ Request error for {url} params={params} -> {exc}")
        return {}


def fetch_teams(sport: str, league_id: int, season: int = SEASON) -> pd.DataFrame:
    url = f"https://v1.{sport}.api-sports.io/teams"
    params = {"league": league_id, "season": season}
    print(f"📊 Fetching {sport.upper()} teams...")
    data = _safe_get_json(url, params)
    resp = data.get("response") or []
    rows = []
    for item in resp:
        if isinstance(item, dict) and "team" in item and isinstance(item["team"], dict):
            team = item["team"]
            rows.append({
                "team_id": team.get("id"),
                "team_name": team.get("name"),
                "team_short": team.get("shortName") or team.get("abbreviation"),
                "city": team.get("city") or team.get("country"),
            })
        elif isinstance(item, dict):
            rows.append({
                "team_id": item.get("id"),
                "team_name": item.get("name"),
                "team_short": item.get("shortName") or item.get("abbreviation"),
                "city": item.get("city") or item.get("country"),
            })
    df = pd.DataFrame(rows)
    if not df.empty:
        df["league_id"] = league_id
        df["sport"] = sport
    else:
        print(f"⚠️ No teams returned for sport={sport} league={league_id} season={season}")
    return df


def fetch_standings(sport: str, league_id: int, season: int = SEASON) -> List[Dict[str, Any]]:
    url = f"https://v1.{sport}.api-sports.io/standings"
    params = {"league": league_id, "season": season}
    print(f"📊 Fetching {sport.upper()} standings for league={league_id} season={season}...")
    data = _safe_get_json(url, params)
    return data.get("response") or []


def fetch_games(sport: str, league_id: int, season: int = SEASON) -> List[Dict[str, Any]]:
    url = f"https://v1.{sport}.api-sports.io/games"
    params = {"league": league_id, "season": season}
    print(f"📊 Fetching {sport.upper()} games for league={league_id} season={season}...")
    data = _safe_get_json(url, params)
    return data.get("response") or []


def fetch_team_statistics(sport: str, league_id: int, team_id: int, season: int = SEASON) -> Dict[str, Any]:
    url = f"https://v1.{sport}.api-sports.io/teams/statistics"
    params = {"league": league_id, "season": season, "team": team_id}
    data = _safe_get_json(url, params)
    resp = data.get("response")
    if not resp:
        return {}
    if isinstance(resp, dict):
        resp["team_id"] = team_id
        return resp
    if isinstance(resp, list) and resp:
        resp[0]["team_id"] = team_id
        return resp[0]
    return {}


def _extract_from_standings_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
    team_info = entry.get("team") or {}
    team_id = team_info.get("id") or entry.get("team_id")
    team_name = team_info.get("name") or entry.get("name")
    played = None
    wins = None
    losses = None
    pf = None
    pa = None

    games = entry.get("all") or entry.get("games") or {}
    if isinstance(games, dict):
        played = games.get("played")
        wins = games.get("win") or games.get("wins")
        losses = games.get("lose") or games.get("losses")
    pf = entry.get("points_for") or entry.get("pointsFor") or (entry.get("points", {}).get("for") if isinstance(entry.get("points"), dict) else None)
    pa = entry.get("points_against") or entry.get("pointsAgainst") or (entry.get("points", {}).get("against") if isinstance(entry.get("points"), dict) else None)

    return {
        "team_id": team_id,
        "team_name": team_name,
        "played": played,
        "wins": wins,
        "losses": losses,
        "points_for": pf,
        "points_against": pa,
    }


def compute_pf_pa_from_games(games: List[Dict[str, Any]]) -> Dict[int, Dict[str, int]]:
    agg: Dict[int, Dict[str, int]] = {}
    for g in games:
        teams = {}
        if "teams" in g and isinstance(g["teams"], dict):
            teams["home"] = {"id": g["teams"]["home"].get("id"), "name": g["teams"]["home"].get("name")}
            teams["away"] = {"id": g["teams"]["away"].get("id"), "name": g["teams"]["away"].get("name")}
        else:
            continue

        scores = g.get("scores") or g.get("score") or {}
        home_score = scores.get("home", {}).get("total") if isinstance(scores.get("home"), dict) else scores.get("home")
        away_score = scores.get("away", {}).get("total") if isinstance(scores.get("away"), dict) else scores.get("away")

        try:
            home_score = int(home_score) if home_score is not None else None
            away_score = int(away_score) if away_score is not None else None
        except Exception:
            home_score = away_score = None

        home_id = teams["home"]["id"]
        away_id = teams["away"]["id"]
        if home_id not in agg:
            agg[home_id] = {"points_for": 0, "points_against": 0, "played": 0, "wins": 0, "losses": 0}
        if away_id not in agg:
            agg[away_id] = {"points_for": 0, "points_against": 0, "played": 0, "wins": 0, "losses": 0}

        if home_score is not None and away_score is not None:
            agg[home_id]["points_for"] += home_score
            agg[home_id]["points_against"] += away_score
            agg[home_id]["played"] += 1
            agg[away_id]["points_for"] += away_score
            agg[away_id]["points_against"] += home_score
            agg[away_id]["played"] += 1
            if home_score > away_score:
                agg[home_id]["wins"] += 1
                agg[away_id]["losses"] += 1
            elif away_score > home_score:
                agg[away_id]["wins"] += 1
                agg[home_id]["losses"] += 1

    return agg


def fetch_league_with_stats(league_key: str, sport: str, league_id: int, season: int = SEASON) -> pd.DataFrame:
    teams_df = fetch_teams(sport, league_id, season)
    if teams_df.empty:
        print(f"⚠️ {league_key.upper()}: No teams returned; skipping league.")
        return pd.DataFrame()

    if "team_id" not in teams_df.columns:
        teams_df = teams_df.rename(columns={"id": "team_id"})

    if sport == "american-football":
        standings = fetch_standings(sport, league_id, season)
        games = fetch_games(sport, league_id, season)

        standings_rows = []
        for group in standings or []:
            if isinstance(group, dict) and "league" in group and "standings" in group:
                nested = group.get("standings", [])
                for sl in nested:
                    if isinstance(sl, list):
                        for entry in sl:
                            standings_rows.append(_extract_from_standings_entry(entry))
            elif isinstance(group, list):
                for entry in group:
                    standings_rows.append(_extract_from_standings_entry(entry))
            elif isinstance(group, dict):
                standings_rows.append(_extract_from_standings_entry(group))

        games_agg = compute_pf_pa_from_games(games)

        merged_rows = []
        for _, tr in teams_df.iterrows():
            tid = tr.get("team_id")
            name = tr.get("team_name")
            stats = next((x for x in standings_rows if x.get("team_id")==tid), {})
            pfpa = games_agg.get(tid, {})
            merged_rows.append({
                "league": league_key.upper(),
                "sport": sport,
                "team_id": tid,
                "team": name,
                "played": stats.get("played"),
                "wins": stats.get("wins"),
                "losses": stats.get("losses"),
                "points_for": stats.get("points_for") or pfpa.get("points_for"),
                "points_against": stats.get("points_against") or pfpa.get("points_against"),
            })

        df_stats = pd.DataFrame(merged_rows)
        out_path = os.path.join(DATA_DIR, f"{league_key}_team_stats.csv")
        df_stats.to_csv(out_path, index=False)
        print(f"✅ {league_key.upper()}: wrote {len(df_stats)} rows to {out_path}")
        return df_stats

    # non-football path
    results = []
    for _, row in teams_df.iterrows():
        tid = row.get("team_id")
        team_name = row.get("team_name")
        stats = fetch_team_statistics(sport, league_id, tid, season) if tid else {}
        if stats:
            gp = stats.get("games", {}).get("played") or stats.get("games_played")
            wins = stats.get("games", {}).get("wins", {}).get("total") if isinstance(stats.get("games", {}).get("wins"), dict) else stats.get("games", {}).get("wins")
            losses = stats.get("games", {}).get("loses", {}).get("total") if isinstance(stats.get("games", {}).get("loses"), dict) else stats.get("games", {}).get("loses")
            pf = stats.get("points", {}).get("for", {}).get("total") if isinstance(stats.get("points", {}).get("for"), dict) else stats.get("points", {}).get("for")
            pa = stats.get("points", {}).get("against", {}).get("total") if isinstance(stats.get("points", {}).get("against"), dict) else stats.get("points", {}).get("against")
        else:
            gp = wins = losses = pf = pa = None

        results.append({
            "league": league_key.upper(),
            "sport": sport,
            "team_id": tid,
            "team": team_name,
            "played": gp,
            "wins": wins,
            "losses": losses,
            "points_for": pf,
            "points_against": pa,
        })
        time.sleep(0.3)

    df_stats = pd.DataFrame(results)
    out_path = os.path.join(DATA_DIR, f"{league_key}_team_stats.csv")
    df_stats.to_csv(out_path, index=False)
    print(f"✅ {league_key.upper()}: wrote {len(df_stats)} rows to {out_path}")
    return df_stats


def main():
    all_dfs: List[pd.DataFrame] = []
    for league_key, (sport, league_id) in LEAGUES.items():
        print(f"\n🏈 Processing league: {league_key.upper()} ({sport}, id={league_id})")
        try:
            df = fetch_league_with_stats(league_key, sport, league_id, season=SEASON)
            if not df.empty:
                all_dfs.append(df)
        except Exception as exc:
            print(f"❌ Error processing {league_key.upper()}: {exc}")

    if not all_dfs:
        print("⚠️ No league produced data. Check API key/permissions/network.")
        return

    combined = pd.concat(all_dfs, ignore_index=True, sort=False)
    combined_path = os.path.join(DATA_DIR, "team_stats_latest.csv")
    combined.to_csv(combined_path, index=False)
    print(f"\n🎉 Combined {len(combined)} teams written to {combined_path}")
    print(f"🕒 Completed at {datetime.utcnow().isoformat()} UTC")


if __name__ == "__main__":
    main()
