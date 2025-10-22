"""
team_stats_fetcher.py
----------------------------------------
Fetches and caches recent NFL team stats using the public
nflverse-pbp play-by-play Parquet files (no API key).

Creates /Data/team_stats_latest.csv containing team-level metrics:
- Offensive/Defensive EPA (z-scored)
- Offensive/Defensive success rate (z-scored)
- Pace (plays per game, z-scored)
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

# Correct RAW URL for nflverse pbp parquet files
NFL_PBP_RAW_URL = (
    "https://raw.githubusercontent.com/nflverse/nflverse-pbp/master/data/play_by_play_{year}.parquet"
)

# Try current season, then fall back to the prior two seasons
CURRENT_YEAR = datetime.utcnow().year
YEAR_PRIORITY = [CURRENT_YEAR, CURRENT_YEAR - 1, CURRENT_YEAR - 2]

OUTPUT_CSV = os.path.join(DATA_DIR, "team_stats_latest.csv")


# ---------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------
def safe_mean(series: pd.Series) -> float:
    return float(series.mean()) if series is not None and len(series) > 0 else 0.0


def _download_parquet_bytes(url: str) -> bytes:
    """Download a parquet file as bytes; raise on non-200."""
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    return resp.content


# ---------------------------------------------------------------------
# MAIN FUNCTIONS
# ---------------------------------------------------------------------
def fetch_nfl_data() -> pd.DataFrame:
    """
    Download nflverse play-by-play parquet for the most recent available season.
    Tries CURRENT_YEAR, then CURRENT_YEAR-1, then CURRENT_YEAR-2.
    """
    last_err = None
    for y in YEAR_PRIORITY:
        url = NFL_PBP_RAW_URL.format(year=y)
        print(f"Attempting to download NFL play-by-play data for {y} ...")
        try:
            data = _download_parquet_bytes(url)
            df = pd.read_parquet(io.BytesIO(data), engine="pyarrow")
            print(f"✅ Successfully loaded {y} data.")
            return df
        except Exception as e:
            print(f"[WARN] Could not load {y}: {e}")
            last_err = e
    raise RuntimeError(f"No nflverse parquet data available. Last error: {last_err}")


def compute_team_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate EPA/success/pace features per team and normalize (z-score)."""
    print("Computing team metrics ...")

    # Offensive metrics (by posteam)
    off = (
        df.groupby("posteam", dropna=False)
        .agg(
            plays=("play_id", "count"),
            epa_off=("epa", safe_mean),
            success_off=("success", safe_mean),
        )
        .reset_index()
        .rename(columns={"posteam": "team"})
    )

    # Defensive metrics (by defteam)
    deff = (
        df.groupby("defteam", dropna=False)
        .agg(
            plays_def=("play_id", "count"),
            epa_def=("epa", safe_mean),
            success_def=("success", safe_mean),
        )
        .reset_index()
        .rename(columns={"defteam": "team"})
    )

    # Merge O + D
    merged = pd.merge(off, deff, on="team", how="outer").fillna(0)

    # Games played (by posteam)
    games = (
        df.groupby("posteam", dropna=False)["game_id"]
        .nunique()
        .reset_index()
        .rename(columns={"posteam": "team", "game_id": "games_played"})
    )
    merged = merged.merge(games, on="team", how="left").fillna({"games_played": 0})

    # Pace = offensive plays per game
    merged["pace"] = merged["plays"] / merged["games_played"].clip(lower=1)

    # Keep only valid team rows (filter out NaN/blank)
    merged = merged[merged["team"].notna() & (merged["team"].astype(str).str.len() > 0)].copy()

    # Normalize feature columns (z-score)
    cols_to_norm = ["epa_off", "epa_def", "success_off", "success_def", "pace"]
    for col in cols_to_norm:
        mu = merged[col].mean()
        sd = merged[col].std()
        merged[col] = (merged[col] - mu) / (sd + 1e-6)

    merged["updated_at"] = datetime.utcnow().isoformat()
    # Order columns
    ordered = [
        "team",
        "plays",
        "plays_def",
        "games_played",
        "epa_off",
        "success_off",
        "epa_def",
        "success_def",
        "pace",
        "updated_at",
    ]
    # Some columns might be missing if input lacked rows; ensure presence
    for c in ordered:
        if c not in merged.columns:
            merged[c] = 0
    merged = merged[ordered]
    return merged


def save_team_stats(df: pd.DataFrame, path: str = OUTPUT_CSV) -> None:
    df.to_csv(path, index=False)
    print(f"💾 Saved team stats to {path}")


def fetch_and_save_team_stats() -> pd.DataFrame:
    """Top-level helper called by predictor_auto before modeling."""
    try:
        df = fetch_nfl_data()
        metrics = compute_team_metrics(df)
        save_team_stats(metrics, OUTPUT_CSV)
        return metrics
    except Exception as e:
        print(f"[WARN] Team stats fetch failed: {e}")
        return pd.DataFrame()


# ---------------------------------------------------------------------
# ENTRY POINT
# ---------------------------------------------------------------------
if __name__ == "__main__":
    fetch_and_save_team_stats()
