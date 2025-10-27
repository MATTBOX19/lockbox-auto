from __future__ import annotations

import os
import time
import requests
import pandas as pd
from datetime import datetime
from typing import Dict, List, Any, Optional

API_KEY = os.getenv("APISPORTS_KEY")
if not API_KEY:
    raise EnvironmentError("Missing $APISPORTS_KEY environment variable. Set APISPORTS_KEY before running.")

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

# requests session for connection pooling
SESSION = requests.Session()
SESSION.headers.update(HEADERS)


def _safe_get_json(url: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """GET the URL and return parsed JSON or empty dict on failure."""
    try:
        r = SESSION.get(url, params=params, timeout=20)
        r.raise_for_status()
        return r.json() if r.content else {}
    except Exception as exc:
        # Keep messages concise: include URL and basic params to help debugging
        print(f"❌ Request error for {url} params={params} -> {exc}")
        return {}


def fetch_teams(sport: str, league_id: int, season: int = SEASON) -> pd.DataFrame:
    """Fetch teams list for a sports league and normalize into DataFrame."""
    url = f"https://v1.{sport}.api-sports.io/teams"
    params = {"league": league_id, "season": season}
    print(f"📊 Fetching {sport.upper()} teams...")
    data = _safe_get_json(url, params)
    resp = data.get("response") or []
    # API returns list of team entries; some wrappers nest under 'team' key
    rows = []
    for item in resp:
        if isinstance(item, dict) and "team" in item and isinstance(item["team"], dict):
            team = item["team"]
            team_record = {
                "team_id": team.get("id"),
                "team_name": team.get("name"),
                "team_short": team.get("shortName") or team.get("abbreviation"),
                "city": team.get("city") or team.get("country"),
            }
        elif isinstance(item, dict):
            # fallback: flatten keys if top-level is already the team
            team_record = {
                "team_id": item.get("id") or item.get("team.id"),
                "team_name": item.get("name") or item.get("team.name"),
                "team_short": item.get("shortName") or item.get("abbreviation"),
                "city": item.get("city") or item.get("country"),
            }
        else:
            continue
        rows.append(team_record)
    df = pd.DataFrame(rows)
    if df.empty:
        print(f"⚠️ No teams returned for sport={sport} league={league_id} season={season}")
    else:
        df["league_id"] = league_id
        df["sport"] = sport
    return df


def fetch_standings(sport: str, league_id: int, season: int = SEASON) -> List[Dict[str, Any]]:
    """Fetch standings for a league (useful for football)."""
    url = f"https://v1.{sport}.api-sports.io/standings"
    params = {"league": league_id, "season": season}
    print(f"📊 Fetching {sport.upper()} standings for league={league_id} season={season}...")
    data = _safe_get_json(url, params)
    return data.get("response") or []


def fetch_games(sport: str, league_id: int, season: int = SEASON) -> List[Dict[str, Any]]:
    """Fetch games for a league/season (helps compute PF/PA if standings don't include totals)."""
    url = f"https://v1.{sport}.api-sports.io/games"
    params = {"league": league_id, "season": season}
    print(f"📊 Fetching {sport.upper()} games for league={league_id} season={season}...")
    data = _safe_get_json(url, params)
    return data.get("response") or []


def fetch_team_statistics(sport: str, league_id: int, team_id: int, season: int = SEASON) -> Dict[str, Any]:
    """Try /teams/statistics endpoint. Return empty dict on failure or missing response."""
    url = f"https://v1.{sport}.api-sports.io/teams/statistics"
    params = {"league": league_id, "season": season, "team": team_id}
    data = _safe_get_json(url, params)
    resp = data.get("response")
    if not resp:
        return {}
    return resp


def _extract_from_standings_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert a single standings entry into a normalized dict with:
      team_id, team_name, wins, losses, played, points_for, points_against
    Handle multiple shapes robustly.
    """
    team_info = entry.get("team") or {}
    team_id = team_info.get("id") or entry.get("team_id") or entry.get("teamId")
    team_name = team_info.get("name") or entry.get("team_name") or entry.get("name")
    played = None
    wins = None
    losses = None
    pf = None
    pa = None

    # Common patterns:
    stats = entry.get("points") or entry.get("form") or {}
    # Some APIs provide games/wins/loses nested under 'all' or 'games'
    games = entry.get("all") or entry.get("games") or entry.get("statistics") or {}
    # wins/losses
    if isinstance(games, dict):
        wins = games.get("win") or games.get("wins") or games.get("wins", {}).get("total") if isinstance(games.get("wins"), dict) else games.get("wins")
        losses = games.get("lose") or games.get("lost") or games.get("losses") or games.get("loses")
        played = games.get("played") or games.get("played", None)
    # points
    pf = entry.get("pointsFor") or entry.get("points_for") or (entry.get("points", {}).get("for") if isinstance(entry.get("points"), dict) else None)
    pa = entry.get("pointsAgainst") or entry.get("points_against") or (entry.get("points", {}).get("against") if isinstance(entry.get("points"), dict) else None)

    # fallback: try nested 'statistics' shapes
    stats_block = entry.get("statistics") or {}
    if isinstance(stats_block, dict):
        pf = pf or stats_block.get("points_for") or stats_block.get("for")
        pa = pa or stats_block.get("points_against") or stats_block.get("against")

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
    """
    Aggregate PF/PA and counts per team from the games list.
    Returns mapping: team_id -> {"points_for": int, "points_against": int, "played": int, "wins": int, "losses": int}
    """
    agg: Dict[int, Dict[str, int]] = {}
    for g in games:
        # each game structure can vary; attempt common keys
        teams = {}
        if "teams" in g and isinstance(g["teams"], dict):
            # some responses include { "home": {...}, "away": {...} }
            for side, t in g["teams"].items():
                tinfo = t or {}
                tid = tinfo.get("id") or tinfo.get("team", {}).get("id")
                name = tinfo.get("name") or tinfo.get("team", {}).get("name")
                teams[side] = {"id": tid, "name": name}
        elif isinstance(g.get("teams"), list):
            # list of two teams
            tlist = g.get("teams") or []
            if len(tlist) >= 2:
                teams["home"] = {"id": tlist[0].get("id"), "name": tlist[0].get("name")}
                teams["away"] = {"id": tlist[1].get("id"), "name": tlist[1].get("name")}
        # scores: some endpoints provide 'scores' with 'home'/'away' and 'total'
        scores = g.get("scores") or g.get("score") or {}
        home_score = None
        away_score = None
        # Try common shapes:
        if isinstance(scores, dict):
            home_score = scores.get("home", {}).get("total") or scores.get("home") or scores.get("homeScore")
            away_score = scores.get("away", {}).get("total") or scores.get("away") or scores.get("awayScore")
        # fallback: direct fields
        if home_score is None:
            home_score = g.get("scores", {}).get("home") if isinstance(g.get("scores"), dict) else g.get("home_score") or g.get("homeScore")
        if away_score is None:
            away_score = g.get("scores", {}).get("away") if isinstance(g.get("scores"), dict) else g.get("away_score") or g.get("awayScore")

        # only consider if we have numeric scores and both teams
        try:
            # coerce to int where possible
            if home_score is not None:
                home_score = int(home_score)
            if away_score is not None:
                away_score = int(away_score)
        except Exception:
            # if not numeric, skip score aggregation for this game
            home_score = None
            away_score = None

        # determine team ids
        home = teams.get("home") or {}
        away = teams.get("away") or {}
        home_id = home.get("id")
        away_id = away.get("id")

        # initialize aggregates
        for tid in (home_id, away_id):
            if not tid:
                continue
            if tid not in agg:
                agg[tid] = {"points_for": 0, "points_against": 0, "played": 0, "wins": 0, "losses": 0}

        if home_id and away_id and home_score is not None and away_score is not None:
            # update points
            agg[home_id]["points_for"] += home_score
            agg[home_id]["points_against"] += away_score
            agg[home_id]["played"] += 1

            agg[away_id]["points_for"] += away_score
            agg[away_id]["points_against"] += home_score
            agg[away_id]["played"] += 1

            # win/loss
            if home_score > away_score:
                agg[home_id]["wins"] += 1
                agg[away_id]["losses"] += 1
            elif away_score > home_score:
                agg[away_id]["wins"] += 1
                agg[home_id]["losses"] += 1
            else:
                # tie handling: neither wins incremented (or you can increment ties if needed)
                pass

    return agg


def fetch_league_with_stats(league_key: str, sport: str, league_id: int, season: int = SEASON) -> pd.DataFrame:
    """
    High-level orchestrator for fetching teams + stats for a league.
    For football (american-football) uses standings + games aggregation.
    For others tries /teams/statistics per team.
    """
    teams_df = fetch_teams(sport, league_id, season)
    if teams_df.empty:
        print(f"⚠️ {league_key.upper()}: No teams returned; skipping league.")
        return pd.DataFrame()

    # Normalize team_id col name
    if "team_id" not in teams_df.columns:
        teams_df = teams_df.rename(columns={"id": "team_id", "team.id": "team_id"})

    # Football special-case: use standings + games for robust PF/PA
    if sport == "american-football":
        standings = fetch_standings(sport, league_id, season)
        games = fetch_games(sport, league_id, season)

        # Build mapping from standings entries
        standings_rows = []
        for group in standings:
            # response often nests groups of table entries; flatten
            # group could be {'league': {...}, 'standings': [[{entry...}, ...]]}
            if isinstance(group, dict) and "league" in group and "standings" in group:
                # iterate nested lists of standings rows
                st_lists = group.get("standings") or []
                for stlist in st_lists:
                    if isinstance(stlist, list):
                        for entry in stlist:
                            standings_rows.append(_extract_from_standings_entry(entry))
            elif isinstance(group, list):
                for entry in group:
                    standings_rows.append(_extract_from_standings_entry(entry))
            elif isinstance(group, dict):
                # maybe directly a single entry
                standings_rows.append(_extract_from_standings_entry(group))

        standings_df = pd.DataFrame(standings_rows)
        # compute pf/pa from games if standings didn't provide totals
        games_agg = compute_pf_pa_from_games(games) if games else {}

        # Merge teams_df with standings_df and fallback to games_agg
        merged = teams_df.merge(standings_df, how="left", left_on="team_id", right_on="team_id")
        # Normalize final output columns explicitly to avoid ambiguous Series truth checks
        final_rows = []
        for _, team_row in merged.iterrows():
            tid = int(team_row["team_id"]) if pd.notna(team_row["team_id"]) else None
            name = team_row.get("team_name") or team_row.get("team.name") or team_row.get("name")
            played = team_row.get("played") if pd.notna(team_row.get("played")) else None
            wins = team_row.get("wins") if pd.notna(team_row.get("wins")) else None
            losses = team_row.get("losses") if pd.notna(team_row.get("losses")) else None
            pf = team_row.get("points_for") if pd.notna(team_row.get("points_for")) else None
            pa = team_row.get("points_against") if pd.notna(team_row.get("points_against")) else None

            # fallback to computed games aggregates
            if tid and (pf is None or pa is None or played is None):
                agg = games_agg.get(tid)
                if agg:
                    pf = pf or agg.get("points_for")
                    pa = pa or agg.get("points_against")
                    played = played or agg.get("played")
                    wins = wins or agg.get("wins")
                    losses = losses or agg.get("losses")

            final_rows.append({
                "league": league_key.upper(),
                "sport": sport,
                "team_id": tid,
                "team": name,
                "played": played,
                "wins": wins,
                "losses": losses,
                "points_for": pf,
                "points_against": pa,
            })

        df_stats = pd.DataFrame(final_rows)
        out_path = os.path.join(DATA_DIR, f"{league_key}_team_stats.csv")
        df_stats.to_csv(out_path, index=False)
        print(f"✅ {league_key.upper()}: wrote {len(df_stats)} rows to {out_path}")
        return df_stats

    # Non-football flow: try per-team /teams/statistics first
    all_stats = []
    for _, row in teams_df.iterrows():
        tid = row.get("team_id") or row.get("id") or row.get("team.id")
        if not tid:
            continue
        stats = fetch_team_statistics(sport, league_id, int(tid), season)
        # If statistics endpoint returned something, try to extract common metrics
        if stats:
            # API shapes vary; be conservative in extraction
            gp = None
            wins = None
            losses = None
            pf = None
            pa = None
            # safe navigation for nested shapes
            games = stats.get("games") or stats.get("all") or {}
            if isinstance(games, dict):
                gp = games.get("played") or games.get("appearences") or games.get("appearances")
                wins = games.get("wins") if isinstance(games.get("wins"), (int, float)) else (games.get("wins", {}).get("total") if isinstance(games.get("wins"), dict) else None)
                losses = games.get("loses") if isinstance(games.get("loses"), (int, float)) else (games.get("loses", {}).get("total") if isinstance(games.get("loses"), dict) else None)

            points = stats.get("points") or {}
            if isinstance(points, dict):
                pf = (points.get("for", {}).get("total") if isinstance(points.get("for"), dict) else points.get("for")) or points.get("for_total")
                pa = (points.get("against", {}).get("total") if isinstance(points.get("against"), dict) else points.get("against")) or points.get("against_total")

            all_stats.append({
                "league": league_key.upper(),
                "sport": sport,
                "team_id": int(tid),
                "team": row.get("team_name") or row.get("team.name") or row.get("name"),
                "played": gp,
                "wins": wins,
                "losses": losses,
                "points_for": pf,
                "points_against": pa,
            })
        else:
            # fallback: include team info only
            all_stats.append({
                "league": league_key.upper(),
                "sport": sport,
                "team_id": int(tid),
                "team": row.get("team_name") or row.get("team.name") or row.get("name"),
                "played": None,
                "wins": None,
                "losses": None,
                "points_for": None,
                "points_against": None,
            })
        # gentle rate limit to avoid hitting API limits
        time.sleep(0.3)

    df_stats = pd.DataFrame(all_stats)
    out_path = os.path.join(DATA_DIR, f"{league_key}_team_stats.csv")
    df_stats.to_csv(out_path, index=False)
    print(f"✅ {league_key.upper()}: wrote {len(df_stats)} rows to {out_path}")
    return df_stats


def main():
    all_dfs: List[pd.DataFrame] = []
    for league_key, (sport, league_id) in LEAGUES.items():
        print(f"\n🏈 Processing league: {league_key.upper()} ({sport}, id={league_id})")
        try:
            df = fetch_league_with_stats(league_key, sport, league_id, SEASON)
            if not df.empty:
                all_dfs.append(df)
        except Exception as exc:
            print(f"❌ Error processing {league_key}: {exc}")

    if not all_dfs:
        print("⚠️ No league produced data. Check API keys, rate limits, and network connectivity.")
        return

    combined = pd.concat(all_dfs, ignore_index=True, sort=False)
    combined_path = os.path.join(DATA_DIR, "team_stats_latest.csv")
    combined.to_csv(combined_path, index=False)
    print(f"\n🎉 Combined {len(combined)} teams written to {combined_path}")
    print(f"🕒 Completed at {datetime.utcnow().isoformat()} UTC")


if __name__ == "__main__":
    main()
