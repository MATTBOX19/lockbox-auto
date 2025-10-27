import os
import requests
import pandas as pd
from datetime import datetime
import time

API_KEY = os.getenv("APISPORTS_KEY")
if not API_KEY:
    raise EnvironmentError("Missing $APISPORTS_KEY environment variable.")

HEADERS = {"x-apisports-key": API_KEY}

# league name → (sport type, league id)
LEAGUES = {
    "nfl": ("american-football", 1),
    "ncaaf": ("american-football", 2),
    "nba": ("basketball", 12),
    "mlb": ("baseball", 1),
    "nhl": ("hockey", 57),
}

DATA_DIR = "Data"
os.makedirs(DATA_DIR, exist_ok=True)


def fetch_teams(sport: str, league_id: int, season=2025) -> pd.DataFrame:
    """Fetch base team info for the league."""
    url = f"https://v1.{sport}.api-sports.io/teams"
    params = {"league": league_id, "season": season}
    print(f"📊 Fetching {sport.upper()} teams...")
    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=20)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"❌ {sport.upper()} teams request failed: {e}")
        return pd.DataFrame()

    if not data.get("response"):
        print(f"⚠️ {sport.upper()}: No team data returned.")
        return pd.DataFrame()

    df = pd.json_normalize(data["response"])
    df["league_id"] = league_id
    df["sport"] = sport
    return df


def fetch_team_stats(sport: str, league_id: int, team_id: int, season=2025) -> dict:
    """Fetch statistics per team (if supported by API-Sports). Fallback to empty dict on errors."""
    url = f"https://v1.{sport}.api-sports.io/teams/statistics"
    params = {"league": league_id, "season": season, "team": team_id}
    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=20)
        r.raise_for_status()
        data = r.json()
        if not data.get("response"):
            return {}
        stats = data["response"]
        stats["team_id"] = team_id
        stats["sport"] = sport
        return stats
    except Exception:
        return {}


def fetch_af_league_stats(league_id: int, season=2025):
    """
    For american-football the API does not reliably support /teams/statistics.
    Instead fetch standings and games for the league and compute per-team aggregates:
      - wins, losses (when available in standings)
      - points_for (pf) and points_against (pa) computed from games boxscores when present
    Returns a pandas DataFrame with columns: team_id, team_name, wins, losses, pf, pa
    """
    sport = "american-football"
    standings_url = f"https://v1.{sport}.api-sports.io/standings"
    games_url = f"https://v1.{sport}.api-sports.io/games"
    params = {"league": league_id, "season": season}

    print(f"📊 Fetching AMERICAN-FOOTBALL standings for league={league_id} season={season}...")
    try:
        r_st = requests.get(standings_url, headers=HEADERS, params=params, timeout=25)
        r_st.raise_for_status()
        st_data = r_st.json().get("response", [])
    except Exception as e:
        print(f"⚠️ Standings request failed: {e}")
        st_data = []

    print(f"📊 Fetching AMERICAN-FOOTBALL games for league={league_id} season={season}...")
    try:
        r_g = requests.get(games_url, headers=HEADERS, params=params, timeout=25)
        r_g.raise_for_status()
        g_data = r_g.json().get("response", [])
    except Exception as e:
        print(f"⚠️ Games request failed: {e}")
        g_data = []

    team_stats = {}

    # Parse standings entries if available to capture wins/losses and team names/ids
    for entry in st_data:
        # many API responses are nested; attempt a few known shapes
        team = entry.get("team") or entry.get("team", {})
        team_id = team.get("id") if isinstance(team, dict) else None
        if not team_id:
            # try other shapes
            try:
                team_id = entry.get("team", {}).get("id")
            except Exception:
                team_id = None
        if not team_id:
            continue
        team_name = team.get("name") if isinstance(team, dict) else None

        # try common standings shapes for wins/losses
        wins = None
        losses = None
        # shape: entry.get('all', {'win': X, 'lose': Y})
        all_stats = entry.get("all") or entry.get("records") or {}
        if isinstance(all_stats, dict):
            wins = all_stats.get("win") or all_stats.get("wins") or all_stats.get("w")
            losses = all_stats.get("lose") or all_stats.get("loses") or all_stats.get("loss")
        # fallback common keys
        if wins is None:
            wins = entry.get("wins") or entry.get("win") or (entry.get("points", {}).get("wins") if isinstance(entry.get("points"), dict) else None)
        if losses is None:
            losses = entry.get("losses") or entry.get("lose") or entry.get("loss")

        # normalize to ints where possible
        try:
            wins = int(wins) if wins is not None else None
        except Exception:
            wins = None
        try:
            losses = int(losses) if losses is not None else None
        except Exception:
            losses = None

        team_stats.setdefault(team_id, {"team_id": team_id, "team_name": team_name, "wins": wins, "losses": losses, "pf": 0, "pa": 0})

    # Use games data to compute points for / against (pf/pa) where boxscore info exists
    for g in g_data:
        # common shapes: g['teams']['home']['id'], g['scores']['home']
        home = g.get("teams", {}).get("home") or {}
        away = g.get("teams", {}).get("away") or {}

        # Extract scores from common shapes
        home_score = None
        away_score = None
        # try several shapes
        if "scores" in g and isinstance(g.get("scores"), dict):
            home_score = g.get("scores", {}).get("home")
            away_score = g.get("scores", {}).get("away")
        if home_score is None or away_score is None:
            # other shape examples
            sc = g.get("score") or g.get("scores") or {}
            home_score = home_score or sc.get("fulltime", {}).get("home") if isinstance(sc, dict) else home_score
            away_score = away_score or sc.get("fulltime", {}).get("away") if isinstance(sc, dict) else away_score
        # try to coerce to int
        try:
            home_score = int(home_score) if home_score is not None else 0
        except Exception:
            home_score = 0
        try:
            away_score = int(away_score) if away_score is not None else 0
        except Exception:
            away_score = 0

        if home and isinstance(home, dict) and home.get("id"):
            hid = home.get("id")
            team_stats.setdefault(hid, {"team_id": hid, "team_name": home.get("name"), "wins": None, "losses": None, "pf": 0, "pa": 0})
            team_stats[hid]["pf"] = team_stats[hid].get("pf", 0) + home_score
            team_stats[hid]["pa"] = team_stats[hid].get("pa", 0) + away_score

        if away and isinstance(away, dict) and away.get("id"):
            aid = away.get("id")
            team_stats.setdefault(aid, {"team_id": aid, "team_name": away.get("name"), "wins": None, "losses": None, "pf": 0, "pa": 0})
            team_stats[aid]["pf"] = team_stats[aid].get("pf", 0) + away_score
            team_stats[aid]["pa"] = team_stats[aid].get("pa", 0) + home_score

    # Convert to DataFrame and normalize columns
    if not team_stats:
        return pd.DataFrame()

    df = pd.DataFrame.from_records(list(team_stats.values()))
    # ensure columns exist
    for col in ["team_id", "team_name", "wins", "losses", "pf", "pa"]:
        if col not in df.columns:
            df[col] = None
    # fill numeric zeros for pf/pa where appropriate
    df["pf"] = df["pf"].fillna(0).astype(int)
    df["pa"] = df["pa"].fillna(0).astype(int)
    # keep meaningful order
    df = df[["team_id", "team_name", "wins", "losses", "pf", "pa"]]
    return df


def fetch_league_with_stats(league: str, sport: str, league_id: int, season=2025) -> pd.DataFrame:
    """Fetch team info and try to enrich with statistics."""
    teams_df = fetch_teams(sport, league_id, season)
    if teams_df.empty:
        print(f"⚠️ {league.upper()}: No teams found — skipping stats.")
        return pd.DataFrame()

    # Special handling for american-football: use standings+games to build stats for whole league
    if sport == "american-football":
        df_stats = fetch_af_league_stats(league_id, season)
        if df_stats.empty:
            print(f"⚠️ {league.upper()}: No AF stats computed; saving team info only.")
            teams_df.to_csv(os.path.join(DATA_DIR, f"{league}_team_stats.csv"), index=False)
            return teams_df

        # Merge teams_df (which has more metadata) with df_stats by team id
        # teams_df may have team id under 'id' or 'team.id'
        if "id" in teams_df.columns:
            merge_left = teams_df.rename(columns={"id": "team_id"})
        elif "team.id" in teams_df.columns:
            merge_left = teams_df.rename(columns={"team.id": "team_id"})
        else:
            merge_left = teams_df.copy()
            merge_left["team_id"] = merge_left.get("team_id") or None

        merged = pd.merge(merge_left, df_stats, how="left", on="team_id", suffixes=("", "_stats"))
        # normalize output columns
        out_cols = {
            "team_id": "team_id",
            "team_name": "team_name",
            "wins": "wins",
            "losses": "losses",
            "pf": "points_for",
            "pa": "points_against",
        }
        # if merged does not have team_name, try from teams data
        if "team_name" not in merged.columns and "name" in merged.columns:
            merged["team_name"] = merged["name"]
        # build final df
        final = pd.DataFrame()
        final["team_id"] = merged["team_id"]
        final["team"] = merged.get("team_name") or merged.get("name") or merged.get("team.name")
        final["league"] = league.upper()
        final["city"] = merged.get("city") if "city" in merged.columns else None
        final["games_played"] = None
        final["wins"] = merged.get("wins")
        final["losses"] = merged.get("losses")
        final["points_for"] = merged.get("pf") if "pf" in merged.columns else merged.get("points_for")
        final["points_against"] = merged.get("pa") if "pa" in merged.columns else merged.get("points_against")

        final.to_csv(os.path.join(DATA_DIR, f"{league}_team_stats.csv"), index=False)
        print(f"✅ {league.upper()}: {len(final)} teams with stats (AF merged).")
        return final

    # For other sports: attempt to fetch per-team statistics via /teams/statistics
    all_stats = []
    for _, row in teams_df.iterrows():
        tid = row.get("id") or row.get("team.id") or row.get("team.id")
        if not tid:
            continue
        stats = fetch_team_stats(sport, league_id, tid, season)
        if stats:
            base = {
                "league": league.upper(),
                "team_id": tid,
                "team": row.get("name") or row.get("team.name"),
                "city": row.get("city") or "",
            }
            # Extract key performance metrics if available
            team_stats = {
                "games_played": stats.get("games", {}).get("played"),
                "wins": stats.get("games", {}).get("wins", {}).get("total")
                if isinstance(stats.get("games", {}).get("wins"), dict)
                else stats.get("games", {}).get("wins"),
                "losses": stats.get("games", {}).get("loses", {}).get("total")
                if isinstance(stats.get("games", {}).get("loses"), dict)
                else stats.get("games", {}).get("loses"),
                "points_for": stats.get("points", {}).get("for", {}).get("total")
                if isinstance(stats.get("points", {}).get("for"), dict)
                else stats.get("points", {}).get("for"),
                "points_against": stats.get("points", {}).get("against", {}).get("total")
                if isinstance(stats.get("points", {}).get("against"), dict)
                else stats.get("points", {}).get("against"),
            }
            all_stats.append({**base, **team_stats})
        time.sleep(0.5)  # gentle rate-limit

    if not all_stats:
        print(f"⚠️ {league.upper()}: No stats found; saving team info only.")
        teams_df.to_csv(os.path.join(DATA_DIR, f"{league}_team_stats.csv"), index=False)
        return teams_df

    df_stats = pd.DataFrame(all_stats)
    df_stats.to_csv(os.path.join(DATA_DIR, f"{league}_team_stats.csv"), index=False)
    print(f"✅ {league.upper()}: {len(df_stats)} teams with stats.")
    return df_stats


def main():
    all_dfs = []

    for league, (sport, league_id) in LEAGUES.items():
        print(f"🏈 Fetching league: {league.upper()} ({sport})")
        df = fetch_league_with_stats(league, sport, league_id)
        if not df.empty:
            all_dfs.append(df)

    if not all_dfs:
        print("⚠️ No leagues returned data. Nothing to merge.")
        return

    combined = pd.concat(all_dfs, ignore_index=True)
    out_path = os.path.join(DATA_DIR, "team_stats_latest.csv")
    combined.to_csv(out_path, index=False)
    print(f"\n🎉 Combined {len(combined)} total teams across {len(all_dfs)} leagues")
    print(f"✅ Saved merged file → {out_path}")
    print(f"🕒 Completed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
PY
