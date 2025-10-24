#!/usr/bin/env python3
"""
lockbox_learn_stats.py
------------------------------------------
Merges LockBox AI predictions with SportsData.io team stats.

Features:
  ✅ Full alias map for NFL, NCAAF, NBA, MLB, NHL
  ✅ Auto-match BestPick / Team1 / Team2 → team stats
  ✅ Outputs metrics.json + performance.json
  ✅ Logs unmatched teams for debugging

Author: LockBox AI
"""

import pandas as pd, json
from pathlib import Path
from datetime import datetime

OUT_DIR = Path("Output")
DATA_DIR = Path("Data")
STATS_FILE = DATA_DIR / "team_stats_latest.csv"
PRED_FILE = OUT_DIR / "Predictions_latest_Explained.csv"
METRICS_FILE = OUT_DIR / "metrics.json"
PERFORMANCE_FILE = OUT_DIR / "performance.json"

# ------------------------------------------------------
# ✅ MASTER ALIAS MAP (all major U.S. sports)
# ------------------------------------------------------

TEAM_ALIASES = {
    # NFL
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
    "JAX": ["JACKSONVILLE JAGUARS", "JAGS", "JAGUARS"],
    "KC": ["KANSAS CITY CHIEFS", "CHIEFS"],
    "LAC": ["LOS ANGELES CHARGERS", "CHARGERS", "LA CHARGERS"],
    "LAR": ["LOS ANGELES RAMS", "RAMS", "LA RAMS"],
    "LV": ["LAS VEGAS RAIDERS", "RAIDERS"],
    "MIA": ["MIAMI DOLPHINS", "DOLPHINS", "FINS"],
    "MIN": ["MINNESOTA VIKINGS", "VIKINGS", "VIKES"],
    "NE": ["NEW ENGLAND PATRIOTS", "PATRIOTS", "PATS"],
    "NO": ["NEW ORLEANS SAINTS", "SAINTS"],
    "NYG": ["NEW YORK GIANTS", "GIANTS"],
    "NYJ": ["NEW YORK JETS", "JETS"],
    "PHI": ["PHILADELPHIA EAGLES", "EAGLES"],
    "PIT": ["PITTSBURGH STEELERS", "STEELERS"],
    "SF": ["SAN FRANCISCO 49ERS", "NINERS", "49ERS"],
    "SEA": ["SEATTLE SEAHAWKS", "SEAHAWKS", "HAWKS"],
    "TB": ["TAMPA BAY BUCCANEERS", "BUCS"],
    "TEN": ["TENNESSEE TITANS", "TITANS"],
    "WAS": ["WASHINGTON COMMANDERS", "COMMANDERS", "WASHINGTON"],

    # NBA
    "ATL_NBA": ["ATLANTA HAWKS", "HAWKS"],
    "BOS_NBA": ["BOSTON CELTICS", "CELTICS"],
    "BKN": ["BROOKLYN NETS", "NETS"],
    "CHA": ["CHARLOTTE HORNETS", "HORNETS"],
    "CHI_NBA": ["CHICAGO BULLS", "BULLS"],
    "CLE_NBA": ["CLEVELAND CAVALIERS", "CAVS"],
    "DAL_NBA": ["DALLAS MAVERICKS", "MAVS"],
    "DEN_NBA": ["DENVER NUGGETS", "NUGGETS"],
    "DET_NBA": ["DETROIT PISTONS", "PISTONS"],
    "GSW": ["GOLDEN STATE WARRIORS", "WARRIORS", "DUBS"],
    "HOU_NBA": ["HOUSTON ROCKETS", "ROCKETS"],
    "IND_NBA": ["INDIANA PACERS", "PACERS"],
    "LAC_NBA": ["LOS ANGELES CLIPPERS", "CLIPPERS"],
    "LAL": ["LOS ANGELES LAKERS", "LAKERS"],
    "MEM": ["MEMPHIS GRIZZLIES", "GRIZZLIES"],
    "MIA_NBA": ["MIAMI HEAT", "HEAT"],
    "MIL": ["MILWAUKEE BUCKS", "BUCKS"],
    "MIN_NBA": ["MINNESOTA TIMBERWOLVES", "WOLVES"],
    "NOP": ["NEW ORLEANS PELICANS", "PELICANS", "PELS"],
    "NYK": ["NEW YORK KNICKS", "KNICKS"],
    "OKC": ["OKLAHOMA CITY THUNDER", "THUNDER"],
    "ORL": ["ORLANDO MAGIC", "MAGIC"],
    "PHI_NBA": ["PHILADELPHIA 76ERS", "SIXERS"],
    "PHX": ["PHOENIX SUNS", "SUNS"],
    "POR": ["PORTLAND TRAIL BLAZERS", "BLAZERS"],
    "SAC": ["SACRAMENTO KINGS", "KINGS"],
    "SAS": ["SAN ANTONIO SPURS", "SPURS"],
    "TOR": ["TORONTO RAPTORS", "RAPTORS"],
    "UTA": ["UTAH JAZZ", "JAZZ"],
    "WAS_NBA": ["WASHINGTON WIZARDS", "WIZARDS"],

    # MLB
    "ATL_MLB": ["ATLANTA BRAVES", "BRAVES"],
    "BOS_MLB": ["BOSTON RED SOX", "RED SOX"],
    "NYY": ["NEW YORK YANKEES", "YANKEES", "YANKS"],
    "LAD": ["LOS ANGELES DODGERS", "DODGERS"],
    "CHC": ["CHICAGO CUBS", "CUBS"],
    "CHW": ["CHICAGO WHITE SOX", "WHITE SOX"],
    "STL": ["ST LOUIS CARDINALS", "CARDINALS"],
    "SF_MLB": ["SAN FRANCISCO GIANTS", "GIANTS"],
    "HOU_MLB": ["HOUSTON ASTROS", "ASTROS"],
    "NYM": ["NEW YORK METS", "METS"],
    "SD": ["SAN DIEGO PADRES", "PADRES"],
    "TB_MLB": ["TAMPA BAY RAYS", "RAYS"],
    "TOR_MLB": ["TORONTO BLUE JAYS", "BLUE JAYS", "JAYS"],
    "PHI_MLB": ["PHILADELPHIA PHILLIES", "PHILLIES"],
    "SEA_MLB": ["SEATTLE MARINERS", "MARINERS"],
    "MIA_MLB": ["MIAMI MARLINS", "MARLINS"],
    "DET_MLB": ["DETROIT TIGERS", "TIGERS"],
    "CIN_MLB": ["CINCINNATI REDS", "REDS"],
    "OAK": ["OAKLAND ATHLETICS", "A'S"],
    "PIT_MLB": ["PITTSBURGH PIRATES", "PIRATES"],
    "BAL_MLB": ["BALTIMORE ORIOLES", "ORIOLES"],
    "WAS_MLB": ["WASHINGTON NATIONALS", "NATIONALS"],
    "ARI_MLB": ["ARIZONA DIAMONDBACKS", "D-BACKS"],
    "MIN_MLB": ["MINNESOTA TWINS", "TWINS"],
    "TEX_MLB": ["TEXAS RANGERS", "RANGERS"],
    "CLE_MLB": ["CLEVELAND GUARDIANS", "GUARDIANS"],
    "MIL_MLB": ["MILWAUKEE BREWERS", "BREWERS"],
    "KC_MLB": ["KANSAS CITY ROYALS", "ROYALS"],

    # NHL
    "BOS_NHL": ["BOSTON BRUINS", "BRUINS"],
    "CHI_NHL": ["CHICAGO BLACKHAWKS", "BLACKHAWKS"],
    "DET_NHL": ["DETROIT RED WINGS", "RED WINGS"],
    "TOR_NHL": ["TORONTO MAPLE LEAFS", "MAPLE LEAFS"],
    "NYR": ["NEW YORK RANGERS", "RANGERS"],
    "PIT_NHL": ["PITTSBURGH PENGUINS", "PENGUINS"],
    "MTL": ["MONTREAL CANADIENS", "CANADIENS"],
    "TB_NHL": ["TAMPA BAY LIGHTNING", "LIGHTNING"],
    "FLA_NHL": ["FLORIDA PANTHERS", "PANTHERS"],
    "EDM": ["EDMONTON OILERS", "OILERS"],
    "VAN": ["VANCOUVER CANUCKS", "CANUCKS"],
    "WPG": ["WINNIPEG JETS", "JETS"],
    "VGK": ["VEGAS GOLDEN KNIGHTS", "KNIGHTS", "VGK"],
    "SEA_NHL": ["SEATTLE KRAKEN", "KRAKEN"],
    "COL_NHL": ["COLORADO AVALANCHE", "AVALANCHE"],
    "OTT": ["OTTAWA SENATORS", "SENATORS"],
    "NSH": ["NASHVILLE PREDATORS", "PREDATORS"],
    "CGY": ["CALGARY FLAMES", "FLAMES"],
    "PHI_NHL": ["PHILADELPHIA FLYERS", "FLYERS"],
    "SJ": ["SAN JOSE SHARKS", "SHARKS"],
    "LAK": ["LOS ANGELES KINGS", "KINGS"],

    # NCAAF (sample core Power 5 + common)
    "ALA": ["ALABAMA CRIMSON TIDE", "ALABAMA", "BAMA"],
    "UGA": ["GEORGIA BULLDOGS", "GEORGIA", "DAWGS"],
    "LSU": ["LSU TIGERS", "LSU"],
    "TEX": ["TEXAS LONGHORNS", "TEXAS", "HORNS"],
    "OU": ["OKLAHOMA SOONERS", "OKLAHOMA"],
    "OSU": ["OHIO STATE BUCKEYES", "OHIO STATE"],
    "MICH": ["MICHIGAN WOLVERINES", "MICHIGAN"],
    "USC": ["USC TROJANS", "SOUTHERN CALIFORNIA"],
    "PSU": ["PENN STATE NITTANY LIONS", "PENN STATE"],
    "ND": ["NOTRE DAME FIGHTING IRISH", "NOTRE DAME"],
    "CLEM": ["CLEMSON TIGERS", "CLEMSON"],
    "FSU": ["FLORIDA STATE SEMINOLES", "FLORIDA STATE"],
    "WISC": ["WISCONSIN BADGERS", "WISCONSIN"],
    "TENN": ["TENNESSEE VOLUNTEERS", "TENNESSEE", "VOLS"],
    "ORE": ["OREGON DUCKS", "OREGON"],
    "WASH": ["WASHINGTON HUSKIES", "WASHINGTON"],
    "IOWA": ["IOWA HAWKEYES", "IOWA"],
    "NEB": ["NEBRASKA CORNHUSKERS", "NEBRASKA", "HUSKERS"],
}

# ------------------------------------------------------
# Helpers
# ------------------------------------------------------

def normalize(name: str):
    if not isinstance(name, str):
        return ""
    return name.strip().upper().replace(".", "").replace("-", "").replace("(", "").replace(")", "").replace("'", "")

def alias_to_abbr(name):
    n = normalize(name)
    for abbr, aliases in TEAM_ALIASES.items():
        for alias in aliases:
            if normalize(alias) in n:
                return abbr
    return None

def safe_mean(series):
    try:
        return round(series.dropna().astype(float).mean(), 3)
    except Exception:
        return 0.0

# ------------------------------------------------------
# Main
# ------------------------------------------------------

def main():
    if not PRED_FILE.exists() or not STATS_FILE.exists():
        print("❌ Missing required files for learning.")
        return

    preds = pd.read_csv(PRED_FILE)
    stats = pd.read_csv(STATS_FILE)

    preds.columns = [c.lower().strip() for c in preds.columns]
    stats.columns = [c.lower().strip() for c in stats.columns]

    team_cols = [c for c in preds.columns if "team" in c or "pick" in c or "bestpick" in c]
    if not team_cols:
        print("⚠️ No suitable team columns found in predictions file. Columns:", preds.columns.tolist())
        return

    print(f"✅ Using team column(s): {team_cols}")
    preds["team_norm"] = preds[team_cols[0]].apply(lambda x: alias_to_abbr(str(x)) or normalize(x))

    # Normalize team names in stats
    for side in ["home", "away", "winner", "team"]:
        if side in stats.columns:
            stats[f"{side}_norm"] = stats[side].apply(lambda x: alias_to_abbr(str(x)) or normalize(x))

    merged_rows, unmatched = [], []

    for _, row in preds.iterrows():
        t = row["team_norm"]
        s = stats[
            (stats.get("home_norm") == t)
            | (stats.get("away_norm") == t)
            | (stats.get("winner_norm") == t)
            | (stats.get("team_norm") == t)
        ]
        if not s.empty:
            s_latest = s.tail(1)
            m = {**row.to_dict()}
            for col in s_latest.columns:
                if col not in ["home", "away", "winner", "date", "sport"]:
                    m[col] = s_latest[col].iloc[0]
            merged_rows.append(m)
        else:
            unmatched.append(t)

    if not merged_rows:
        print("⚠️ No matching games found to merge.")
        return

    merged = pd.DataFrame(merged_rows)
    print(f"✅ Merged {len(merged)} predictions with team stat records")

    summary = {
        "timestamp": datetime.utcnow().isoformat(),
        "games": len(merged),
        "avg_edge": safe_mean(merged.get("edge", pd.Series(dtype=float))),
        "avg_confidence": safe_mean(merged.get("confidence", pd.Series(dtype=float))),
    }

    with open(METRICS_FILE, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"🧠 Updated metrics.json with {summary['games']} merged games")

    perf = {
        "updated": summary["timestamp"],
        "summary": {
            "edge": summary["avg_edge"],
            "confidence": summary["avg_confidence"]
        }
    }
    with open(PERFORMANCE_FILE, "w") as f:
        json.dump(perf, f, indent=2)
    print("📊 performance.json written")

    if unmatched:
        print(f"⚠️ Unmatched teams ({len(unmatched)}): {sorted(set(unmatched))[:30]}")

if __name__ == "__main__":
    main()
