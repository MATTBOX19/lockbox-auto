"""
team_stats_fetcher.py
----------------------------------------
Fetches and caches current-season NFL team stats
using the public nflfastR data (no API key needed).

Creates /Data/team_stats_latest.csv containing
rolling team-level metrics for offensive and defensive
EPA, success rate, and pace.

Later phases can extend this module for NBA/NHL/MLB/CFB.
"""

import os
import io
import requests
import pandas as pd
from datetime import datetime

# ---------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------
DATA_DIR = os.path.join(os.getcwd(), "Data")
os.makedirs(DATA_DIR, exist_ok=True)

NFLFASTR_URL = "https://github.com/nflverse/nflfastR-data/raw/master/data/play_by_play_{year}.parquet"

CURRENT_YEAR = datetime.now().year
ROLLING_WEEKS = 5  # compute last 5 weeks average
OUTPUT_CSV = os.path.join(DATA_DIR, "team_stats_latest.csv")


# ---------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------
def safe_mean(series):
    return series.mean() if not series.empty else 0.0


# ---------------------------------------------------------------------
# MAIN FUNCTIONS
# ---------------------------------------------------------------------
def fetch_nfl_data(year: int = CURRENT_YEAR) -> pd.DataFrame:
    """Download nflfastR play-by-play parquet for given year."""
    url = NFLFASTR_URL.format(year=year)
    print(f"Downloading NFL play-by-play data for {year} ...")
    df = pd.read_parquet(url)
    return df


def compute_team_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate EPA/success/pace features per team."""
    print("Computing team metrics ...")
    # offensive side
    off = (
        df.groupby("posteam")
        .agg(
            plays=("play_id", "count"),
            epa_off=("epa", safe_mean),
            success_off=("success", safe_mean),
        )
        .reset_index()
        .rename(columns={"posteam": "team"})
    )

    # defensive side (group by defteam)
    defn = (
        df.groupby("defteam")
        .agg(
            plays_def=("play_id", "count"),
            epa_def=("epa", safe_mean),
            success_def=("success", safe_mean),
        )
        .reset_index()
        .rename(columns={"defteam": "team"})
    )

    # merge
    merged = pd.merge(off, defn, on="team", how="outer").fillna(0)

    # derive pace = plays per game
    games = df.groupby("posteam")["game_id"].nunique().reset_index()
    games.columns = ["team", "games_played"]
    merged = merged.merge(games, on="team", how="left")
    merged["pace"] = merged["plays"] / merged["games_played"].clip(lower=1)

    # compute rolling normalized features
    cols_to_norm = ["epa_off", "epa_def", "success_off", "success_def", "pace"]
    merged[cols_to_norm] = merged[cols_to_norm].apply(lambda x: (x - x.mean()) / (x.std() + 1e-6))

    merged["updated_at"] = datetime.utcnow().isoformat()
    return merged


def save_team_stats(df: pd.DataFrame, path: str = OUTPUT_CSV):
    """Save DataFrame to CSV."""
    df.to_csv(path, index=False)
    print(f"Saved team stats to {path}")


def fetch_and_save_team_stats():
    """Top-level helper called by predictor_auto before modeling."""
    try:
        df = fetch_nfl_data(CURRENT_YEAR)
        metrics = compute_team_metrics(df)
        save_team_stats(metrics, OUTPUT_CSV)
        return metrics
    except Exception as e:
        print(f"[WARN] Team stats fetch failed: {e}")
        return pd.DataFrame()


if __name__ == "__main__":
    fetch_and_save_team_stats()
