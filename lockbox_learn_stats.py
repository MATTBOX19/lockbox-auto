#!/usr/bin/env python3
"""
lockbox_learn_stats.py — Merge LockBox predictions with SportsData.io stats

Automated Daily Metrics Learner:
  • Normalizes team names (supports NFL, NCAAF, NBA, MLB, NHL)
  • Merges latest predictions ↔ team stats
  • Updates metrics.json and performance.json
"""

import pandas as pd, json, re
from pathlib import Path
from datetime import datetime

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
    "LAC": ["LOS ANGELES CHARGERS", "CHARGERS"],
    "LAR": ["LOS ANGELES RAMS", "RAMS"],
    "LV": ["LAS VEGAS RAIDERS", "RAIDERS"],
    "MIA": ["MIAMI DOLPHINS", "DOLPHINS"],
    "MIN": ["MINNESOTA VIKINGS", "VIKINGS"],
    "NE": ["NEW ENGLAND PATRIOTS", "PATRIOTS"],
    "NO": ["NEW ORLEANS SAINTS", "SAINTS"],
    "NYG": ["NEW YORK GIANTS", "GIANTS"],
    "NYJ": ["NEW YORK JETS", "JETS"],
    "PHI": ["PHILADELPHIA EAGLES", "EAGLES"],
    "PIT": ["PITTSBURGH STEELERS", "STEELERS"],
    "SF": ["SAN FRANCISCO 49ERS", "NINERS", "49ERS"],
    "SEA": ["SEATTLE SEAHAWKS", "SEAHAWKS"],
    "TB": ["TAMPA BAY BUCCANEERS", "BUCCANEERS", "BUCS"],
    "TEN": ["TENNESSEE TITANS", "TITANS"],
    "WAS": ["WASHINGTON COMMANDERS", "COMMANDERS", "WASHINGTON"],

    # --- NBA ---
    "ATL_NBA": ["ATLANTA HAWKS", "HAWKS"],
    "BOS_NBA": ["BOSTON CELTICS", "CELTICS"],
    "BKN": ["BROOKLYN NETS", "NETS"],
    "CHA": ["CHARLOTTE HORNETS", "HORNETS"],
    "CHI_NBA": ["CHICAGO BULLS", "BULLS"],
    "CLE_NBA": ["CLEVELAND CAVALIERS", "CAVS"],
    "DAL_NBA": ["DALLAS MAVERICKS", "MAVS"],
    "DEN_NBA": ["DENVER NUGGETS", "NUGGETS"],
    "DET_NBA": ["DETROIT PISTONS", "PISTONS"],
    "GSW": ["GOLDEN STATE WARRIORS", "WARRIORS"],
    "HOU_NBA": ["HOUSTON ROCKETS", "ROCKETS"],
    "IND_NBA": ["INDIANA PACERS", "PACERS"],
    "LAC_NBA": ["LOS ANGELES CLIPPERS", "CLIPPERS"],
    "LAL": ["LOS ANGELES LAKERS", "LAKERS"],
    "MEM": ["MEMPHIS GRIZZLIES", "GRIZZLIES"],
    "MIA_NBA": ["MIAMI HEAT", "HEAT"],
    "MIL": ["MILWAUKEE BUCKS", "BUCKS"],
    "MIN_NBA": ["MINNESOTA TIMBERWOLVES", "TIMBERWOLVES"],
    "NYK": ["NEW YORK KNICKS", "KNICKS"],
    "OKC": ["OKLAHOMA CITY THUNDER", "THUNDER"],
    "ORL": ["ORLANDO MAGIC", "MAGIC"],
    "PHX": ["PHOENIX SUNS", "SUNS"],
    "POR": ["PORTLAND TRAIL BLAZERS", "BLAZERS"],
    "SAC": ["SACRAMENTO KINGS", "KINGS"],
    "SAS": ["SAN ANTONIO SPURS", "SPURS"],
    "TOR": ["TORONTO RAPTORS", "RAPTORS"],
    "UTA": ["UTAH JAZZ", "JAZZ"],
    "WAS_NBA": ["WASHINGTON WIZARDS", "WIZARDS"],

    # --- MLB ---
    "ATL_MLB": ["ATLANTA BRAVES", "BRAVES"],
    "BOS_MLB": ["BOSTON RED SOX", "RED SOX"],
    "NYY": ["NEW YORK YANKEES", "YANKEES"],
    "CHC": ["CHICAGO CUBS", "CUBS"],
    "LAD": ["LOS ANGELES DODGERS", "DODGERS"],
    "SF_MLB": ["SAN FRANCISCO GIANTS", "GIANTS"],
    "HOU_MLB": ["HOUSTON ASTROS", "ASTROS"],
    "SD": ["SAN DIEGO PADRES", "PADRES"],
    "PHI_MLB": ["PHILADELPHIA PHILLIES", "PHILLIES"],
    "BAL_MLB": ["BALTIMORE ORIOLES", "ORIOLES"],
    "TB_MLB": ["TAMPA BAY RAYS", "RAYS"],
    "NYM": ["NEW YORK METS", "METS"],

    # --- NHL ---
    "BOS_NHL": ["BOSTON BRUINS", "BRUINS"],
    "COL_NHL": ["COLORADO AVALANCHE", "AVALANCHE"],
    "DET_NHL": ["DETROIT RED WINGS", "RED WINGS"],
    "EDM": ["EDMONTON OILERS", "OILERS"],
    "CHI_NHL": ["CHICAGO BLACKHAWKS", "BLACKHAWKS"],
    "NYR": ["NEW YORK RANGERS", "RANGERS"],
    "PIT_NHL": ["PITTSBURGH PENGUINS", "PENGUINS"],
    "TOR_NHL": ["TORONTO MAPLE LEAFS", "MAPLE LEAFS"],

    # --- NCAAF (partial sample, 130+ supported in full table) ---
    "ALA": ["ALABAMA CRIMSON TIDE", "BAMA"],
    "UGA": ["GEORGIA BULLDOGS", "DAWGS"],
    "MICH": ["MICHIGAN WOLVERINES", "WOLVERINES"],
    "OHST": ["OHIO STATE BUCKEYES", "BUCKEYES"],
    "TEX": ["TEXAS LONGHORNS", "HORNS"],
    "LSU": ["LSU TIGERS"],
    "ND": ["NOTRE DAME FIGHTING IRISH", "IRISH"],
    "USC": ["SOUTHERN CALIFORNIA TROJANS", "TROJANS"],
    "CLEM": ["CLEMSON TIGERS", "CLEMSON"],
}

# --- Utility helpers ---
def normalize_team(t):
    if not isinstance(t, str):
        return ""
    t = re.sub(r"[^A-Za-z0-9]", "", t).upper()
    for abbr, aliases in TEAM_MAP.items():
        if t == abbr or any(t == re.sub(r"[^A-Za-z0-9]", "", a) for a in aliases):
            return abbr
    return t

def safe_mean(series):
    try:
        return round(series.dropna().astype(float).mean(), 3)
    except Exception:
        return 0.0

def main():
    if not PRED_FILE.exists() or not STATS_FILE.exists():
        print("❌ Missing required files.")
        return

    preds = pd.read_csv(PRED_FILE)
    stats = pd.read_csv(STATS_FILE)

    preds.columns = [c.lower().strip() for c in preds.columns]
    stats.columns = [c.lower().strip() for c in stats.columns]

    team_col = None
    for c in ["bestpick", "team1", "home", "team"]:
        if c in preds.columns:
            team_col = c
            break
    if not team_col:
        print(f"⚠️ No usable team column found. Columns: {list(preds.columns)}")
        return

    print(f"✅ Using team column(s): ['{team_col}']")

    preds["team_norm"] = preds[team_col].astype(str).apply(normalize_team)
    stats["team_norm"] = stats["team"].astype(str).apply(normalize_team) if "team" in stats.columns else None

    merged_rows = []
    unmatched = set()

    for _, row in preds.iterrows():
        t = row["team_norm"]
        if not t:
            continue
        s = stats[stats["team_norm"] == t]
        if not s.empty:
            merged = {**row.to_dict()}
            for col in ["epa_off", "epa_def", "success_off", "success_def", "pace"]:
                if col in s.columns:
                    merged[col] = float(s[col].iloc[0])
            merged_rows.append(merged)
        else:
            unmatched.add(t)

    if not merged_rows:
        print("⚠️ No matching games found to merge.")
        return

    merged = pd.DataFrame(merged_rows)
    print(f"✅ Merged {len(merged)} predictions with team stat records")

    summary = {
        "timestamp": datetime.utcnow().isoformat(),
        "games": len(merged),
        "avg_edge": safe_mean(merged["edge"]) if "edge" in merged else 0,
        "avg_confidence": safe_mean(merged["confidence"]) if "confidence" in merged else 0,
        "avg_epa_off": safe_mean(merged.get("epa_off", pd.Series(dtype=float))),
        "avg_epa_def": safe_mean(merged.get("epa_def", pd.Series(dtype=float))),
        "avg_success_off": safe_mean(merged.get("success_off", pd.Series(dtype=float))),
        "avg_success_def": safe_mean(merged.get("success_def", pd.Series(dtype=float))),
        "avg_pace": safe_mean(merged.get("pace", pd.Series(dtype=float))),
    }

    with open(METRICS_FILE, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"🧠 Updated metrics.json with {summary['games']} merged games")

    perf = {
        "updated": summary["timestamp"],
        "overall": {
            "edge": summary["avg_edge"],
            "confidence": summary["avg_confidence"],
        },
    }
    with open(PERFORMANCE_FILE, "w") as f:
        json.dump(perf, f, indent=2)
    print("📊 performance.json written")

    if unmatched:
        print(f"⚠️ Unmatched teams ({len(unmatched)}): {sorted(unmatched)[:20]}...")

if __name__ == "__main__":
    main()
