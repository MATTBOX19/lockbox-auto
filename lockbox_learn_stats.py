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
TEAM_MAP = {
    # --- NFL ---
    "ARI": ["ARIZONA CARDINALS", "CARDINALS", "CARDS"],
    "ATL": ["ATLANTA FALCONS", "FALCONS"],
    "BAL": ["BALTIMORE RAVENS", "RAVENS"],
    "BUF": ["BUFFALO BILLS", "BILLS"],
    "CAR": ["CAROLINA PANTHERS", "PANTHERS"],
    "CHI": ["CHICAGO BEARS", "BEARS"],
    "CIN": ["CINCINNATI BENGALS", "BENGALS"],
    "CLE": ["CLEVELAND BROWNS", "BROWNS"],
    "DAL": ["DALLAS COWBOYS", "COWBOYS", "BOYS"],
    "DEN": ["DENVER BRONCOS", "BRONCOS"],
    "DET": ["DETROIT LIONS", "LIONS"],
    "GB": ["GREEN BAY PACKERS", "PACKERS"],
    "HOU": ["HOUSTON TEXANS", "TEXANS"],
    "IND": ["INDIANAPOLIS COLTS", "COLTS"],
    "JAX": ["JACKSONVILLE JAGUARS", "JAGS"],
    "KC": ["KANSAS CITY CHIEFS", "CHIEFS"],
    "LAC": ["LOS ANGELES CHARGERS", "CHARGERS", "L.A. CHARGERS"],
    "LAR": ["LOS ANGELES RAMS", "RAMS", "L.A. RAMS"],
    "LV": ["LAS VEGAS RAIDERS", "RAIDERS"],
    "MIA": ["MIAMI DOLPHINS", "DOLPHINS", "FINS"],
    "MIN": ["MINNESOTA VIKINGS", "VIKINGS", "VIKES"],
    "NE": ["NEW ENGLAND PATRIOTS", "PATRIOTS", "PATS"],
    "NO": ["NEW ORLEANS SAINTS", "SAINTS"],
    "NYG": ["NEW YORK GIANTS", "GIANTS", "NYG"],
    "NYJ": ["NEW YORK JETS", "JETS", "NYJ"],
    "PHI": ["PHILADELPHIA EAGLES", "EAGLES"],
    "PIT": ["PITTSBURGH STEELERS", "STEELERS"],
    "SF": ["SAN FRANCISCO 49ERS", "49ERS", "NINERS"],
    "SEA": ["SEATTLE SEAHAWKS", "SEAHAWKS", "HAWKS"],
    "TB": ["TAMPA BAY BUCCANEERS", "BUCCANEERS", "BUCS"],
    "TEN": ["TENNESSEE TITANS", "TITANS"],
    "WAS": ["WASHINGTON COMMANDERS", "COMMANDERS", "WASHINGTON"],

    # --- NBA ---
    "ATL_NBA": ["ATLANTA HAWKS", "HAWKS"],
    "BOS_NBA": ["BOSTON CELTICS", "CELTICS", "CS"],
    "BKN": ["BROOKLYN NETS", "NETS"],
    "CHA": ["CHARLOTTE HORNETS", "HORNETS"],
    "CHI_NBA": ["CHICAGO BULLS", "BULLS"],
    "CLE_NBA": ["CLEVELAND CAVALIERS", "CAVS"],
    "DAL_NBA": ["DALLAS MAVERICKS", "MAVERICKS", "MAVS"],
    "DEN_NBA": ["DENVER NUGGETS", "NUGGETS", "NUGS"],
    "DET_NBA": ["DETROIT PISTONS", "PISTONS"],
    "GSW": ["GOLDEN STATE WARRIORS", "WARRIORS", "DUBS"],
    "HOU_NBA": ["HOUSTON ROCKETS", "ROCKETS"],
    "IND_NBA": ["INDIANA PACERS", "PACERS"],
    "LAC_NBA": ["LOS ANGELES CLIPPERS", "CLIPPERS", "CLIPS"],
    "LAL": ["LOS ANGELES LAKERS", "LAKERS"],
    "MEM": ["MEMPHIS GRIZZLIES", "GRIZZLIES", "GRIZZ"],
    "MIA_NBA": ["MIAMI HEAT", "HEAT"],
    "MIL": ["MILWAUKEE BUCKS", "BUCKS"],
    "MIN_NBA": ["MINNESOTA TIMBERWOLVES", "TIMBERWOLVES", "WOLVES"],
    "NOP": ["NEW ORLEANS PELICANS", "PELICANS", "PELS"],
    "NYK": ["NEW YORK KNICKS", "KNICKS"],
    "OKC": ["OKLAHOMA CITY THUNDER", "THUNDER"],
    "ORL": ["ORLANDO MAGIC", "MAGIC"],
    "PHI_NBA": ["PHILADELPHIA 76ERS", "SIXERS", "76ERS"],
    "PHX": ["PHOENIX SUNS", "SUNS"],
    "POR": ["PORTLAND TRAIL BLAZERS", "BLAZERS"],
    "SAC": ["SACRAMENTO KINGS", "KINGS"],
    "SAS": ["SAN ANTONIO SPURS", "SPURS"],
    "TOR": ["TORONTO RAPTORS", "RAPTORS", "RAPS"],
    "UTA": ["UTAH JAZZ", "JAZZ"],
    "WAS_NBA": ["WASHINGTON WIZARDS", "WIZARDS"],

    # --- MLB ---
    "ARI_MLB": ["ARIZONA DIAMONDBACKS", "DIAMONDBACKS", "D-BACKS"],
    "ATL_MLB": ["ATLANTA BRAVES", "BRAVES"],
    "BAL_MLB": ["BALTIMORE ORIOLES", "ORIOLES", "OS"],
    "BOS_MLB": ["BOSTON RED SOX", "RED SOX", "SOX"],
    "CHC": ["CHICAGO CUBS", "CUBS"],
    "CHW": ["CHICAGO WHITE SOX", "WHITE SOX", "SOX"],
    "CIN_MLB": ["CINCINNATI REDS", "REDS"],
    "CLE_MLB": ["CLEVELAND GUARDIANS", "GUARDIANS"],
    "COL": ["COLORADO ROCKIES", "ROCKIES"],
    "DET_MLB": ["DETROIT TIGERS", "TIGERS"],
    "HOU_MLB": ["HOUSTON ASTROS", "ASTROS", "STROS"],
    "KC": ["KANSAS CITY ROYALS", "ROYALS"],
    "LAA": ["LOS ANGELES ANGELS", "ANGELS", "HALOS"],
    "LAD": ["LOS ANGELES DODGERS", "DODGERS"],
    "MIA_MLB": ["MIAMI MARLINS", "MARLINS"],
    "MIL_MLB": ["MILWAUKEE BREWERS", "BREWERS", "BREW CREW"],
    "MIN_MLB": ["MINNESOTA TWINS", "TWINS"],
    "NYM": ["NEW YORK METS", "METS"],
    "NYY": ["NEW YORK YANKEES", "YANKEES", "YANKS"],
    "OAK": ["OAKLAND ATHLETICS", "ATHLETICS", "AS"],
    "PHI_MLB": ["PHILADELPHIA PHILLIES", "PHILLIES", "PHILS"],
    "PIT_MLB": ["PITTSBURGH PIRATES", "PIRATES", "BUCS"],
    "SD": ["SAN DIEGO PADRES", "PADRES"],
    "SF_MLB": ["SAN FRANCISCO GIANTS", "GIANTS"],
    "SEA_MLB": ["SEATTLE MARINERS", "MARINERS", "MS"],
    "STL": ["ST LOUIS CARDINALS", "CARDINALS", "CARDS"],
    "TB_MLB": ["TAMPA BAY RAYS", "RAYS"],
    "TEX": ["TEXAS RANGERS", "RANGERS"],
    "TOR_MLB": ["TORONTO BLUE JAYS", "BLUE JAYS", "JAYS"],
    "WSH_MLB": ["WASHINGTON NATIONALS", "NATIONALS", "NATS"],

    # --- NHL ---
    "ANA": ["ANAHEIM DUCKS", "DUCKS"],
    "ARI_NHL": ["ARIZONA COYOTES", "COYOTES", "YOTES"],
    "BOS_NHL": ["BOSTON BRUINS", "BRUINS"],
    "BUF_NHL": ["BUFFALO SABRES", "SABRES"],
    "CAR_NHL": ["CAROLINA HURRICANES", "HURRICANES", "CANES"],
    "CBJ": ["COLUMBUS BLUE JACKETS", "BLUE JACKETS", "JACKETS"],
    "CGY": ["CALGARY FLAMES", "FLAMES"],
    "CHI_NHL": ["CHICAGO BLACKHAWKS", "BLACKHAWKS", "HAWKS"],
    "COL_NHL": ["COLORADO AVALANCHE", "AVALANCHE", "AVS"],
    "DAL_NHL": ["DALLAS STARS", "STARS"],
    "DET_NHL": ["DETROIT RED WINGS", "RED WINGS", "WINGS"],
    "EDM_NHL": ["EDMONTON OILERS", "OILERS"],
    "FLA": ["FLORIDA PANTHERS", "PANTHERS"],
    "LAK": ["LOS ANGELES KINGS", "KINGS"],
    "MIN_NHL": ["MINNESOTA WILD", "WILD"],
    "MTL": ["MONTREAL CANADIENS", "CANADIENS", "HABS"],
    "NSH": ["NASHVILLE PREDATORS", "PREDATORS", "PREDS"],
    "NJD": ["NEW JERSEY DEVILS", "DEVILS"],
    "NYI": ["NEW YORK ISLANDERS", "ISLANDERS", "ISLES"],
    "NYR_NHL": ["NEW YORK RANGERS", "RANGERS"],
    "OTT": ["OTTAWA SENATORS", "SENATORS", "SENS"],
    "PHI_NHL": ["PHILADELPHIA FLYERS", "FLYERS"],
    "PIT_NHL": ["PITTSBURGH PENGUINS", "PENGUINS", "PENS"],
    "SEA_NHL": ["SEATTLE KRAKEN", "KRAKEN"],
    "SJS": ["SAN JOSE SHARKS", "SHARKS"],
    "STL_NHL": ["ST LOUIS BLUES", "BLUES"],
    "TBL": ["TAMPA BAY LIGHTNING", "LIGHTNING", "BOLTS"],
    "TOR_NHL": ["TORONTO MAPLE LEAFS", "MAPLE LEAFS", "LEAFS"],
    "VAN": ["VANCOUVER CANUCKS", "CANUCKS"],
    "VGK": ["VEGAS GOLDEN KNIGHTS", "GOLDEN KNIGHTS", "VGK"],
    "WPG": ["WINNIPEG JETS", "JETS"],
    "WSH_NHL": ["WASHINGTON CAPITALS", "CAPITALS", "CAPS"],

    # --- NCAAF (subset / examples) ---
    "ALA": ["ALABAMA CRIMSON TIDE", "ALABAMA", "BAMA"],
    "UGA": ["GEORGIA BULLDOGS", "GEORGIA", "DAWGS"],
    "LSU": ["LSU TIGERS", "LOUISIANA STATE"],
    "TEX": ["TEXAS LONGHORNS", "TEXAS", "HORNS"],
    "OU": ["OKLAHOMA SOONERS", "OKLAHOMA"],
    "OSU": ["OHIO STATE BUCKEYES", "OHIO STATE", "BUCKEYES"],
    # ... (keep the remainder of your NCAAF map as you had it) ...
}


# --- Utility helpers + improved logging/debugging ---
def setup_logger(out_dir: Path, name: str = "lockbox"):
    out_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(name)
    # If handlers already present (module re-imported), return same logger
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
    """Clean and normalize team string to match TEAM_MAP aliases."""
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
    """Return list of (candidate, score) pairs ordered best->worst."""
    if not choices:
        return []
    if HAS_RAPIDFUZZ:
        results = process.extract(pred_name, choices, scorer=fuzz.token_sort_ratio, limit=top_n)
        out = []
        for r in results:
            if len(r) >= 2:
                out.append((r[0], float(r[1])))
        return out
    else:
        matches = get_close_matches(pred_name, choices, n=top_n, cutoff=0.0)
        out = []
        for m in matches:
            score = int(SequenceMatcher(a=pred_name, b=m).ratio() * 100)
            out.append((m, float(score)))
        return out


def dump_debug_files(out_dir: Path, logger, preds: pd.DataFrame, stats: pd.DataFrame, merged: pd.DataFrame, unmatched: set):
    """Write CSVs to OUT_DIR to inspect merged/unmatched and fuzzy candidates."""
    out_dir.mkdir(parents=True, exist_ok=True)

    # merged (may be empty)
    merged_path = out_dir / "merged_debug.csv"
    try:
        merged.to_csv(merged_path, index=False)
        logger.info("Wrote merged debug rows => %s (%d rows)", merged_path, len(merged))
    except Exception as e:
        logger.exception("Failed writing merged_debug.csv: %s", e)

    # unmatched list
    unmatched_list = sorted(list(unmatched))
    un_path = out_dir / "unmatched_sample.csv"
    try:
        pd.DataFrame(unmatched_list, columns=["unmatched"]).to_csv(un_path, index=False)
        logger.info("Wrote unmatched list => %s (%d entries)", un_path, len(unmatched_list))
    except Exception as e:
        logger.exception("Failed writing unmatched_sample.csv: %s", e)

    # Save some sample stats keys for quick inspection
    stats_keys_path = out_dir / "stats_team_keys_sample.csv"
    try:
        if "team_key" in stats.columns:
            pd.Series(sorted(stats["team_key"].dropna().unique()), name="stats_team_key").to_csv(stats_keys_path, index=False)
            logger.info("Wrote stats team_key sample => %s", stats_keys_path)
    except Exception as e:
        logger.exception("Failed writing stats_team_keys_sample.csv: %s", e)

    # Prepare choices robustly: prefer stats.team_key, else fallback to stats.team (or empty Series)
    if "team_key" in stats.columns:
        choices_series = stats["team_key"].dropna().astype(str)
    else:
        team_col = stats.get("team", pd.Series(dtype=str))
        choices_series = pd.Series(team_col).dropna().astype(str)

    choices = list(choices_series.unique())

    # Generate fuzzy candidates for top unmatched (limit 200 to avoid huge file)
    candidates = []
    for pred in unmatched_list[:200]:
        cands = _get_fuzzy_candidates(pred, choices, top_n=8)
        for cand, score in cands:
            candidates.append({"pred": pred, "candidate": cand, "score": score})

    cand_path = out_dir / "unmatched_fuzzy_candidates.csv"
    try:
        if candidates:
            pd.DataFrame(candidates).to_csv(cand_path, index=False)
            logger.info("Wrote fuzzy candidate matches => %s (%d rows)", cand_path, len(candidates))
        else:
            logger.info("No fuzzy candidates generated (empty unmatched or stats choices).")
    except Exception as e:
        logger.exception("Failed writing unmatched_fuzzy_candidates.csv: %s", e)


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

    # --- Normalize possible sport/league naming ---
    if "sport" in stats.columns:
        stats = stats.rename(columns={"sport": "league"})

   team_col = next((c for c in ["BestPick", "bestpick", "team1", "home", "team"] if c in preds.columns), None)
    if not team_col:
        logger.error("No usable team column found. Columns: %s", list(preds.columns))
        return

    logger.info("Using team column: %s", team_col)

    # --- improved normalization & merge logic ---
    def normalize_name(x: str) -> str:
        if not isinstance(x, str):
            return ""
        x = x.upper().strip()
        x = re.sub(r"\(.*?\)", "", x)  # remove (ATS), (ML), etc.
        x = re.sub(r"[^A-Z0-9 ]+", "", x)
        x = re.sub(r"\s+", " ", x)
        return x.strip()

    # build a quick alias → abbr lookup
    ALIAS_TO_ABBR = {}
    for abbr, aliases in TEAM_MAP.items():
        ALIAS_TO_ABBR[abbr] = abbr
        for alias in aliases:
            ALIAS_TO_ABBR[normalize_name(alias)] = abbr

    def to_key(s: str) -> str:
        n = normalize_name(s)
        return ALIAS_TO_ABBR.get(n, n)  # mapped abbr if known, else cleaned text

    # normalize predictions team names
    preds["team_key"] = preds[team_col].astype(str).apply(to_key)
    logger.info("Predictions: %d rows, sample team_key: %s", len(preds), preds["team_key"].dropna().unique()[:8].tolist())

    # --- handle game-level stats with Home/Away ---
    if "team" in stats.columns:
        stats["team_key"] = stats["team"].astype(str).apply(to_key)
    elif "home" in stats.columns and "away" in stats.columns:
        home_cols = [c for c in ["home", "league", "homescore", "homeyards", "hometurnovers", "homepossession"] if c in stats.columns]
        away_cols = [c for c in ["away", "league", "awayscore", "awayyards", "awayturnovers", "awaypossession"] if c in stats.columns]
        home_df = stats[home_cols].copy()
        # map present home columns to unified names (defensive if some missing)
        rename_home = {}
        if "home" in home_df.columns:
            rename_home["home"] = "team"
        if "homescore" in home_df.columns:
            rename_home["homescore"] = "score"
        if "homeyards" in home_df.columns:
            rename_home["homeyards"] = "yards"
        if "hometurnovers" in home_df.columns:
            rename_home["hometurnovers"] = "turnovers"
        if "homepossession" in home_df.columns:
            rename_home["homepossession"] = "possession"
        home_df = home_df.rename(columns=rename_home)

        away_df = stats[away_cols].copy()
        rename_away = {}
        if "away" in away_df.columns:
            rename_away["away"] = "team"
        if "awayscore" in away_df.columns:
            rename_away["awayscore"] = "score"
        if "awayyards" in away_df.columns:
            rename_away["awayyards"] = "yards"
        if "awayturnovers" in away_df.columns:
            rename_away["awayturnovers"] = "turnovers"
        if "awaypossession" in away_df.columns:
            rename_away["awaypossession"] = "possession"
        away_df = away_df.rename(columns=rename_away)

        # unify available columns
        common_cols = list(dict.fromkeys([c for c in (home_df.columns.tolist() + away_df.columns.tolist()) if c in ["team","league","score","yards","turnovers","possession"]]))
        stats = pd.concat([home_df[common_cols], away_df[common_cols]], ignore_index=True, sort=False)
        stats["team_key"] = stats["team"].astype(str).apply(to_key)
    else:
        stats["team_key"] = ""
    logger.info("Stats: %d rows, sample team_key: %s", len(stats), stats["team_key"].dropna().unique()[:8].tolist())

    merged_rows, unmatched = [], set()

    for _, prow in preds.iterrows():
        tkey = prow.get("team_key", "")
        if not tkey:
            continue

        # match on abbreviation
        s = stats[stats["team_key"] == tkey]

        if s.empty:
            unmatched.add(tkey)
            continue

        srow = s.iloc[0]
        merged = {**prow.to_dict()}

        # store whichever stat columns exist in this stats file
        for col in ["score", "yards", "turnovers", "possession"]:
            if col in s.columns:
                try:
                    merged[col] = float(srow[col])
                except Exception:
                    merged[col] = srow[col]
        merged_rows.append(merged)

    if not merged_rows:
        logger.warning("No matching games found to merge.")
        # still dump debug to help diagnose
        dump_debug_files(OUT_DIR, logger, preds, stats, pd.DataFrame(), unmatched)
        return

    merged = pd.DataFrame(merged_rows)
    logger.info("Merged %d predictions with team stat records", len(merged))

    # write metrics/perf as before
    summary = {
        "timestamp": datetime.utcnow().isoformat(),
        "games": len(merged),
        "avg_edge": safe_mean(merged.get("edge", pd.Series(dtype=float))),
        "avg_confidence": safe_mean(merged.get("confidence", pd.Series(dtype=float))),
        "avg_epa_off": safe_mean(merged.get("epa_off", pd.Series(dtype=float))),
        "avg_epa_def": safe_mean(merged.get("epa_def", pd.Series(dtype=float))),
        "avg_success_off": safe_mean(merged.get("success_off", pd.Series(dtype=float))),
        "avg_success_def": safe_mean(merged.get("success_def", pd.Series(dtype=float))),
        "avg_pace": safe_mean(merged.get("pace", pd.Series(dtype=float))),
    }

    try:
        with open(METRICS_FILE, "w") as f:
            json.dump(summary, f, indent=2)
        logger.info("Updated metrics.json with %d merged games", summary["games"])
    except Exception as e:
        logger.exception("Failed writing metrics.json: %s", e)

    perf = {
        "updated": summary["timestamp"],
        "overall": {"edge": summary["avg_edge"], "confidence": summary["avg_confidence"]},
    }
    try:
        with open(PERFORMANCE_FILE, "w") as f:
            json.dump(perf, f, indent=2)
        logger.info("performance.json written")
    except Exception as e:
        logger.exception("Failed writing performance.json: %s", e)

    # dump helpful debug artifacts for inspection
    dump_debug_files(OUT_DIR, logger, preds, stats, merged, unmatched)

    if unmatched:
        logger.warning(
            "Unmatched teams (%d). See %s/unmatched_sample.csv and unmatched_fuzzy_candidates.csv for details.",
            len(unmatched),
            OUT_DIR,
        )


if __name__ == "__main__":
    main()
