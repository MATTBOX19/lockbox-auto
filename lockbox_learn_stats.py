#!/usr/bin/env python3
"""
lockbox_learn_stats.py — Merge LockBox predictions with SportsData.io stats

Automated Daily Metrics Learner:
  • Normalizes team names (supports NFL, NCAAF, NBA, MLB, NHL)
  • Merges latest predictions ↔ team stats (with partial-match support)
  • Updates metrics.json and performance.json
"""

import json
import re
from pathlib import Path
from datetime import datetime
import pandas as pd
import logging
from logging.handlers import RotatingFileHandler
from difflib import get_close_matches, SequenceMatcher

# try optional high-quality fuzzy library
try:
    from rapidfuzz import process, fuzz  # type: ignore
    HAS_RAPIDFUZZ = True
except Exception:
    HAS_RAPIDFUZZ = False

# -------- Configuration / file paths ----------
OUT_DIR = Path("Output")
DATA_DIR = Path("Data")
STATS_FILE = DATA_DIR / "team_stats_latest.csv"
PRED_FILE = OUT_DIR / "Predictions_latest_Explained.csv"
METRICS_FILE = OUT_DIR / "metrics.json"
PERFORMANCE_FILE = OUT_DIR / "performance.json"

# --- TEAM MAP (All Major Sports) ---
# [keep your entire TEAM_MAP dictionary here exactly as in your file]
TEAM_MAP = {...}  # unchanged, your full dictionary stays the same

# --- Utility helpers ---
def setup_logger(out_dir: Path, name: str = "lockbox"):
    out_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    fh = RotatingFileHandler(out_dir / "lockbox_run.log", maxBytes=2_000_000, backupCount=5)
    fh.setFormatter(fmt)
    logger.addHandler(sh)
    logger.addHandler(fh)
    return logger

def normalize_team(t):
    if not isinstance(t, str):
        return ""
    t = t.strip().upper()
    t = re.sub(r"\(.*?\)", "", t)
    t = re.sub(r"[^A-Z0-9]", "", t)
    t = re.sub(r"(NFL|NBA|MLB|NHL|NCAAF)$", "", t)
    for abbr, aliases in TEAM_MAP.items():
        clean_aliases = [re.sub(r"[^A-Z0-9]", "", a.upper()) for a in aliases]
        if t == abbr or t in clean_aliases:
            return abbr
    return t

def safe_mean(series):
    try:
        return round(series.dropna().astype(float).mean(), 3)
    except Exception:
        return 0.0

def _get_fuzzy_candidates(pred_name: str, choices: list, top_n=5):
    if not choices:
        return []
    if HAS_RAPIDFUZZ:
        results = process.extract(pred_name, choices, scorer=fuzz.token_sort_ratio, limit=top_n)
        return [(r[0], float(r[1])) for r in results if len(r) >= 2]
    matches = get_close_matches(pred_name, choices, n=top_n, cutoff=0.0)
    return [(m, float(SequenceMatcher(a=pred_name, b=m).ratio() * 100)) for m in matches]

def dump_debug_files(out_dir: Path, logger, preds: pd.DataFrame, stats: pd.DataFrame, merged: pd.DataFrame, unmatched: set):
    out_dir.mkdir(parents=True, exist_ok=True)
    merged_path = out_dir / "merged_debug.csv"
    try:
        merged.to_csv(merged_path, index=False)
        logger.info("Wrote merged debug rows => %s (%d rows)", merged_path, len(merged))
    except Exception as e:
        logger.exception("Failed writing merged_debug.csv: %s", e)
    unmatched_list = sorted(list(unmatched))
    un_path = out_dir / "unmatched_sample.csv"
    try:
        pd.DataFrame(unmatched_list, columns=["unmatched"]).to_csv(un_path, index=False)
        logger.info("Wrote unmatched list => %s (%d entries)", un_path, len(unmatched_list))
    except Exception as e:
        logger.exception("Failed writing unmatched_sample.csv: %s", e)
    stats_keys_path = out_dir / "stats_team_keys_sample.csv"
    try:
        if "team_key" in stats.columns:
            pd.Series(sorted(stats["team_key"].dropna().unique()), name="stats_team_key").to_csv(stats_keys_path, index=False)
            logger.info("Wrote stats team_key sample => %s", stats_keys_path)
    except Exception as e:
        logger.exception("Failed writing stats_team_keys_sample.csv: %s", e)

# --- main logic ----------------------------------------------------------
def main():
    logger = setup_logger(OUT_DIR)
    logger.info("Starting lockbox_learn_stats run")

    if not PRED_FILE.exists() or not STATS_FILE.exists():
        logger.error("Missing required files: %s, %s", PRED_FILE, STATS_FILE)
        return

    preds = pd.read_csv(PRED_FILE)
    stats = pd.read_csv(STATS_FILE)

    preds.columns = [c.lower().strip() for c in preds.columns]
    stats.columns = [c.lower().strip() for c in stats.columns]

    if "sport" in stats.columns:
        stats = stats.rename(columns={"sport": "league"})

    team_col = next((c for c in ["bestpick", "team1", "home", "team"] if c in preds.columns), None)
    if not team_col:
        logger.error("No usable team column found. Columns: %s", list(preds.columns))
        return
    logger.info("Using team column: %s", team_col)

    def normalize_name(x: str) -> str:
        if not isinstance(x, str):
            return ""
        x = x.upper().strip()
        x = re.sub(r"\(.*?\)", "", x)
        x = re.sub(r"[^A-Z0-9 ]+", "", x)
        x = re.sub(r"\s+", " ", x)
        return x.strip()

    alias_to_abbr = {}
    for abbr, aliases in TEAM_MAP.items():
        alias_to_abbr[abbr] = abbr
        for alias in aliases:
            alias_to_abbr[normalize_name(alias)] = abbr

    def to_key(s: str) -> str:
        n = normalize_name(s)
        return alias_to_abbr.get(n, n)

    # ✅ fixed indentation below
    def bestpick_to_teamkey(val: str) -> str:
        """Clean BestPick entries like 'Miami Dolphins (ATS)' or 'Over (OU)'."""
        raw = str(val).strip()
        up = raw.upper()
        if up.startswith("OVER") or up.startswith("UNDER"):
            return ""
        cleaned = re.sub(r"\(.*?\)", "", up)
        cleaned = re.sub(r"[^A-Z0-9 ]+", "", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return alias_to_abbr.get(cleaned, "")

    if team_col == "bestpick":
        preds["team_key"] = preds[team_col].astype(str).apply(bestpick_to_teamkey)
    else:
        preds["team_key"] = preds[team_col].astype(str).apply(to_key)

    # [keep rest of your merging and JSON logic exactly as in your file]

if __name__ == "__main__":
    main()
