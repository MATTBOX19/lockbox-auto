"""
af_adapter.py

Lightweight adapter to compute team statistics/features from api-sports
fixtures/results so you don't rely on a non-existent `teams/statistics` endpoint.

Dependencies: requests, math, typing, datetime
(These are already present in your requirements: requests, pandas, numpy, etc.)
"""

from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
import requests
import math

# ---- Helpers ----
def _iso_to_dt(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None

def safe_int(x) -> Optional[int]:
    try:
        if x is None or x == "":
            return None
        return int(x)
    except Exception:
        return None

# ---- Fetching from API ----
API_BASE = "https://v1.american-football.api-sports.io"

def fetch_fixtures(api_key: str, league: int, season: int, team: int, status: Optional[str]=None, limit: int=200) -> List[Dict[str,Any]]:
    """
    Pull fixtures for a team (past & upcoming). status optional (e.g. 'NS','FT').
    Returns list of fixture dicts as returned by the API.
    """
    headers = {"x-apisports-key": api_key}
    params = {"league": league, "season": season, "team": team, "page":1, "limit": limit}
    if status:
        params["status"] = status
    url = f"{API_BASE}/fixtures"
    r = requests.get(url, headers=headers, params=params, timeout=30)
    r.raise_for_status()
    payload = r.json()
    # api returns payload['response'] list of fixtures
    return payload.get("response", [])

# ---- Stats computation ----
def compute_team_stats(fixtures: List[Dict[str,Any]], team_id: int, lookback: int = 10) -> Dict[str,Any]:
    """
    Compute simple, deterministic features for a team from fixture list:
      - games_played, wins, draws, losses
      - goals_for, goals_against, avg_goals_for, avg_goals_against
      - last_n form string and numeric score (W=1,D=0.5,L=0)
      - home/away splits on last games
    Assumes fixtures contains both past and future games; only uses finished games (status 'FT' or 'AET' or 'PEN').
    """
    finished_statuses = {"FT", "AET", "PEN"}
    # gather last finished fixtures involving team
    past = []
    for f in fixtures:
        # API structure: f['teams']['home']['id'], f['teams']['away']['id']; f['score'] contains periods and totals
        status = f.get("fixture", {}).get("status", {}).get("short") or f.get("fixture", {}).get("status", {}).get("elapsed")
        if status not in finished_statuses and status != "FT":
            continue
        # Determine if team in fixture
        h = f.get("teams", {}).get("home", {})
        a = f.get("teams", {}).get("away", {})
        if h.get("id") == team_id or a.get("id") == team_id:
            past.append(f)

    # sort by date ascending
    past.sort(key=lambda x: _iso_to_dt(x.get("fixture", {}).get("date")) or datetime.min)

    stats = {
        "games": 0, "wins": 0, "draws": 0, "losses": 0,
        "goals_for": 0, "goals_against": 0,
        "avg_goals_for": 0.0, "avg_goals_against": 0.0,
        "recent_form": "", "recent_numeric": 0.0,
        "home_games": 0, "away_games": 0, "home_wins": 0, "away_wins": 0
    }

    # Only use last `lookback` finished games for form and averages
    last_games = past[-lookback:] if len(past) >= 1 else []

    for f in last_games:
        stats["games"] += 1
        teams = f.get("teams", {})
        scores = f.get("score", {})
        # totals may be under 'fulltime' or 'total' in different APIs; try common keys
        home_score = safe_int(scores.get("home")) or safe_int(scores.get("fulltime", {}).get("home")) or safe_int(scores.get("total", {}).get("home"))
        away_score = safe_int(scores.get("away")) or safe_int(scores.get("fulltime", {}).get("away")) or safe_int(scores.get("total", {}).get("away"))
        if home_score is None or away_score is None:
            # skip incomplete score
            continue

        home_id = teams.get("home", {}).get("id")
        away_id = teams.get("away", {}).get("id")
        is_home = (home_id == team_id)

        gf = home_score if is_home else away_score
        ga = away_score if is_home else home_score

        stats["goals_for"] += gf
        stats["goals_against"] += ga

        if gf > ga:
            stats["wins"] += 1
            if is_home:
                stats["home_wins"] += 1
            else:
                stats["away_wins"] += 1
            stats["recent_form"] += "W"
            stats["recent_numeric"] += 1.0
        elif gf == ga:
            stats["draws"] += 1
            stats["recent_form"] += "D"
            stats["recent_numeric"] += 0.5
        else:
            stats["losses"] += 1
            stats["recent_form"] += "L"
            stats["recent_numeric"] += 0.0

        if is_home:
            stats["home_games"] += 1
        else:
            stats["away_games"] += 1

    if stats["games"] > 0:
        stats["avg_goals_for"] = stats["goals_for"] / stats["games"]
        stats["avg_goals_against"] = stats["goals_against"] / stats["games"]
        # normalize recent_numeric to 0..1
        stats["recent_numeric"] = stats["recent_numeric"] / stats["games"]

    # goal difference
    stats["gd"] = stats["goals_for"] - stats["goals_against"]

    # add sample rating: combine recent_numeric and gd scaled
    stats["rating"] = (stats["recent_numeric"] * 0.7) + (math.tanh(stats["gd"] / max(1, stats["games"])) * 0.3)

    return stats

# ---- Feature engineering for a match ----
def match_features(team1_stats: Dict[str,Any], team2_stats: Dict[str,Any]) -> Dict[str,Any]:
    """
    Build simple features for a predicted match between team1 and team2.
    Returns a dict of numeric features you can feed into an AI model.
    """
    f = {}
    f["t1_games"] = team1_stats.get("games",0)
    f["t2_games"] = team2_stats.get("games",0)
    f["diff_rating"] = team1_stats.get("rating",0.0) - team2_stats.get("rating",0.0)
    f["diff_avg_gf"] = team1_stats.get("avg_goals_for",0.0) - team2_stats.get("avg_goals_for",0.0)
    f["diff_avg_ga"] = team1_stats.get("avg_goals_against",0.0) - team2_stats.get("avg_goals_against",0.0)
    f["diff_gd_per_game"] = (team1_stats.get("gd",0)/max(1,team1_stats.get("games",1))) - (team2_stats.get("gd",0)/max(1,team2_stats.get("games",1)))
    f["diff_recent_numeric"] = team1_stats.get("recent_numeric",0.0) - team2_stats.get("recent_numeric",0.0)
    # simple heuristic probability (sigmoid on diff_rating)
    prob = 1.0 / (1.0 + math.exp(-4.0 * f["diff_rating"]))  # scale factor 4 sharpens
    f["heuristic_prob_team1"] = prob
    f["heuristic_prob_team2"] = 1 - prob
    # edge estimation (in points): map probability to expected edge roughly
    f["edge_est"] = (prob - 0.5) * 100
    return f

# ---- Combined convenience: fetch -> compute -> features ----
def build_match_features_from_api(api_key: str, league: int, season: int, team1: int, team2: int, lookback:int=10) -> Dict[str,Any]:
    """
    Fetch last results for both teams and compute features for a match.
    Returns { 'team1_stats':..., 'team2_stats':..., 'features': ... }
    """
    # fetch both teams fixtures (past finished games)
    f1 = fetch_fixtures(api_key, league, season, team1, status=None, limit=200)
    f2 = fetch_fixtures(api_key, league, season, team2, status=None, limit=200)
    s1 = compute_team_stats(f1, team1, lookback=lookback)
    s2 = compute_team_stats(f2, team2, lookback=lookback)
    feats = match_features(s1, s2)
    return {"team1_stats": s1, "team2_stats": s2, "features": feats}
