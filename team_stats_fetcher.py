"""
team_stats_fetcher.py
----------------------------------------
Robust team stats fetcher for NFL play-by-play.

Strategy:
1) Try nfl_data_py (preferred) to import play-by-play.
2) If that fails, attempt to download parquet bytes from raw.githubusercontent
   for recent years (current, current-1, current-2).
3) If a source succeeds, compute team-level features and save to Data/team_stats_latest.csv.

Notes:
- Upstream data availability (nflverse releases / raw parquet) can vary. If you see
  repeated 404s, that means the nflverse hosts haven't published the season parquet yet.
- To use nfl_data_py, install: pip install nfl-data-py
"""

import os
import io
from datetime import datetime

import pandas as pd
import requests

# ---------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------
DATA_DIR = os.path.join(os.getcwd(), "Data")
os.makedirs(DATA_DIR, exist_ok=True)

# Raw content path (try these if nfl_data_py isn't available or fails)
RAW_PBP_URL_TEMPLATE = (
    "https://raw.githubusercontent.com/nflverse/nflverse-pbp/master/data/play_by_play_{year}.parquet"
)

# Years to try (current, last, -2)
CURRENT_YEAR = datetime.utcnow().year
YEAR_PRIORITY = [CURRENT_YEAR, CURRENT_YEAR - 1, CURRENT_YEAR - 2]

OUTPUT_CSV = os.path.join(DATA_DIR, "team_stats_latest.csv")


# ---------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------
def safe_mean(series: pd.Series) -> float:
    try:
        return float(series.mean()) if series is not None and len(series) > 0 else 0.0
    except Exception:
        return 0.0


def _download_parquet_bytes(url: str) -> bytes:
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    return resp.content


# ---------------------------------------------------------------------
# FETCHING STRATEGIES
# ---------------------------------------------------------------------
def try_nfl_data_py(years):
    """
    Try to fetch pbp using nfl_data_py (preferred).
    This requires the pip package 'nfl-data-py' installed (pip install nfl-data-py).
    Returns a DataFrame or raises.
    """
    try:
        import nfl_data_py as nfl  # type: ignore
    except Exception as e:
        raise RuntimeError(
            "nfl_data_py import failed. Install with: pip install nfl-data-py"
        ) from e

    # preferred function name variants used in the wild: import_pbp_data or import_pbp
    func = None
    if hasattr(nfl, "import_pbp_data"):
        func = nfl.import_pbp_data
    elif hasattr(nfl, "import_pbp"):
        func = nfl.import_pbp
    else:
        raise RuntimeError("nfl_data_py found but no import_pbp_data/import_pbp function available.")

    last_error = None
    for y in years:
        print(f"[nfl_data_py] Attempting to import play-by-play for {y} ...")
        try:
            try:
                df = func([y])
            except TypeError:
                try:
                    df = func(years=[y])
                except TypeError:
                    df = func(y)
            if not isinstance(df, pd.DataFrame):
                df = pd.DataFrame(df)
            print(f"✅ nfl_data_py loaded {y} (rows={len(df)})")
            return df
        except Exception as e:
            last_error = e
            print(f"[nfl_data_py] could not load {y}: {e}")
            continue

    raise RuntimeError(f"nfl_data_py failed for years {years}. Last error: {last_error}")


def try_raw_parquet(years):
    """
    Try to download raw parquet files from raw.githubusercontent (nflverse-pbp).
    Returns DataFrame or raises.
    """
    last_err = None
    for y in years:
        url = RAW_PBP_URL_TEMPLATE.format(year=y)
        print(f"[raw-http] Attempting to download play-by-play for {y} ...")
        try:
            data = _download_parquet_bytes(url)
            df = pd.read_parquet(io.BytesIO(data), engine="pyarrow")
            print(f"✅ raw parquet loaded {y} (rows={len(df)})")
            return df
        except Exception as e:
            last_err = e
            print(f"[raw-http] Could not load {y}: {e}")
            continue
    raise RuntimeError(f"No raw parquet available for years {years}. Last error: {last_err}")


def fetch_pbp_prefer_nfl_data_py(years=YEAR_PRIORITY):
    """
    Try nfl_data_py first (if installed). If it fails, fall back to raw parquet.
    """
    try:
        print("Trying nfl_data_py (preferred) ...")
        return try_nfl_data_py(years)
    except Exception as e:
        print(f"[info] nfl_data_py path failed: {e}")

    try:
        print("Falling back to raw parquet downloads ...")
        return try_raw_parquet(years)
    except Exception as e:
        raise RuntimeError(f"All PBP fetch strategies failed. Last error: {e}")


# ---------------------------------------------------------------------
# PROCESSING
# ---------------------------------------------------------------------
def compute_team_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate EPA/success/pace features per team and normalize (z-score)."""
    print("Computing team metrics ...")

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

    merged = pd.merge(off, deff, on="team", how="outer").fillna(0)

    games = (
        df.groupby("posteam", dropna=False)["game_id"]
        .nunique()
        .reset_index()
        .rename(columns={"posteam": "team", "game_id": "games_played"})
    )
    merged = merged.merge(games, on="team", how="left").fillna({"games_played": 0})

    merged["pace"] = merged["plays"] / merged["games_played"].clip(lower=1)
    merged = merged[merged["team"].notna() & (merged["team"].astype(str).str.len() > 0)].copy()

    cols_to_norm = ["epa_off", "epa_def", "success_off", "success_def", "pace"]
    for col in cols_to_norm:
        mu = merged[col].mean()
        sd = merged[col].std()
        merged[col] = (merged[col] - mu) / (sd + 1e-6)

    merged["updated_at"] = datetime.utcnow().isoformat()

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
    for c in ordered:
        if c not in merged.columns:
            merged[c] = 0
    merged = merged[ordered]
    return merged


def save_team_stats(df: pd.DataFrame, path: str = OUTPUT_CSV) -> None:
    df.to_csv(path, index=False)
    print(f"💾 Saved team stats to {path}")


# ---------------------------------------------------------------------
# TOP-LEVEL
# ---------------------------------------------------------------------
def fetch_and_save_team_stats():
    """Main entry point called by worker/predictor."""
    try:
        pbp = fetch_pbp_prefer_nfl_data_py(YEAR_PRIORITY)
        metrics = compute_team_metrics(pbp)
        save_team_stats(metrics, OUTPUT_CSV)
        return metrics
    except Exception as e:
        print("[ERROR] Team stats fetch failed.")
        print("Details:", e)
        print()
        print("Common causes:")
        print(" - The nflverse release for the requested seasons is not yet published.")
        print(" - The Python package `nfl_data_py` is not installed or is unable to retrieve the season.")
        print()
        print("Try these steps:")
        print(" 1) Ensure pyarrow and requests are installed (these are in requirements). Example:")
        print("      pip install pyarrow requests")
        print(" 2) Install nfl_data_py (preferred):")
        print("      pip install nfl-data-py")
        print(" 3) Re-run this script. If the upstream release isn't published, you may need to wait")
        print("    for nflverse to publish the season or use an alternate data source (Kaggle/NFLsavant).")
        return pd.DataFrame()


# ---------------------------------------------------------------------
# ENTRY POINT
# ---------------------------------------------------------------------
if __name__ == "__main__":
    fetch_and_save_team_stats()
