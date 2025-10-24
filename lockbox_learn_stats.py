#!/usr/bin/env python3
"""
lockbox_learn_stats.py — Combine LockBox predictions with SportsData.io stats

Purpose:
  • Merge AI predictions with real game + stat data.
  • Learn which team-level metrics correlate with outcomes.
  • Update metrics.json and performance.json for dashboard display.
  • Supports NFL, NCAAF, NBA, NHL, and MLB.
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

# ------------------ TEAM MAPS ------------------ #

TEAM_MAP = {
    # --- NFL ---
    "ARI": "ARIZONACARDINALS", "ATL": "ATLANTAFALCONS", "BAL": "BALTIMORERAVENS",
    "BUF": "BUFFALOBILLS", "CAR": "CAROLINAPANTHERS", "CHI": "CHICAGOBEARS",
    "CIN": "CINCINNATIBENGALS", "CLE": "CLEVELANDBROWNS", "DAL": "DALLASCOWBOYS",
    "DEN": "DENVERBRONCOS", "DET": "DETROITLIONS", "GB": "GREENBAYPACKERS",
    "HOU": "HOUSTONTEXANS", "IND": "INDIANAPOLISCOLTS", "JAX": "JACKSONVILLEJAGUARS",
    "KC": "KANSASCITYCHIEFS", "LV": "LASVEGASRAIDERS", "LAC": "LACHARGERS",
    "LAR": "LARAMS", "MIA": "MIAMIDOLPHINS", "MIN": "MINNESOTAVIKINGS",
    "NE": "NEWENGLANDPATRIOTS", "NO": "NEWORLEANSSAINTS", "NYG": "NEWYORKGIANTS",
    "NYJ": "NEWYORKJETS", "PHI": "PHILADELPHIAEAGLES", "PIT": "PITTSBURGHSTEELERS",
    "SEA": "SEATTLESEAHAWKS", "SF": "SANFRANCISCO49ERS", "TB": "TAMPABAYBUCCANEERS",
    "TEN": "TENNESSEETITANS", "WAS": "WASHINGTONCOMMANDERS",

    # --- NCAAF (Top 50 programs + common) ---
    "ALABAMA": "ALABAMACRIMSONTIDE", "GEORGIA": "GEORGIABULLDOGS", "LSU": "LSUTIGERS",
    "TEXAS": "TEXASLONGHORNS", "OKLAHOMA": "OKLAHOMASOONERS", "OHIOSTATE": "OHIOSTATEBUCKEYES",
    "MICHIGAN": "MICHIGANWOLVERINES", "FLORIDA": "FLORIDAGATORS", "FLORIDAST": "FLORIDASTATESEMINOLES",
    "MIAMIFL": "MIAMIHURRICANES", "NOTREDAME": "NOTREDAMEFIGHTINGIRISH", "USC": "USCTROJANS",
    "UCLA": "UCLABRUINS", "OREGON": "OREGONDUCKS", "WASHINGTON": "WASHINGTONHUSKIES",
    "AUBURN": "AUBURNTIGERS", "TEXASA&M": "TEXASAMAGGIES", "TENNESSEE": "TENNESSEEVOLUNTEERS",
    "CLEMSON": "CLEMSONTIGERS", "PENNSTATE": "PENNSTATENITTANYLIONS",
    "WISCONSIN": "WISCONSINBADGERS", "IOWA": "IOWAHAWKEYES", "MINNESOTA": "MINNESOTAGO PHERS",
    "ILLINOIS": "ILLINOISFIGHTINGILLINI", "PURDUE": "PURDUEBOILERMAKERS",
    "BAYLOR": "BAYLORBEARS", "TCU": "TCUHORNFROGS", "TEXASTECH": "TEXASTECHREDRAIDERS",
    "OKSTATE": "OKLAHOMASTATECOWBOYS", "KANSAS": "KANSASJAYHAWKS", "KANSASSTATE": "KANSASSTATEWILDCATS",
    "NEBRASKA": "NEBRASKACORN HUSKERS", "COLORADO": "COLORADOBUFFALOES", "UTAH": "UTAHRUNNINUTES",
    "ARIZONAST": "ARIZONASTATESUNDEVILS", "ARIZONA": "ARIZONAWILDCATS",
    "BOISESTATE": "BOISESTATEBRONCOS", "SMU": "SMUMUSTANGS", "UCF": "UCFFKNIGHTS",
    "CINCINNATI": "CINCINNATIBEARCATS", "LOUISVILLE": "LOUISVILLECARDINALS",
    "KENTUCKY": "KENTUCKYWILDCATS", "MISSOURI": "MISSOURITIGERS",
    "OLEMISS": "OLEMISSREBELS", "MISSISSIPPISTATE": "MISSISSIPPISTATBULLDOGS",
    "SOUTHCAROLINA": "SOUTHCAROLINAGAMECOCKS", "VANDERBILT": "VANDERBILTCOMMODORES",

    # --- NBA ---
    "ATLANTAHAWKS": "ATLANTAHAWKS", "BOSTONCELTICS": "BOSTONCELTICS",
    "BROOKLYNNETS": "BROOKLYNNETS", "CHARLOTTESHORNETS": "CHARLOTTESHORNETS",
    "CHICAGOBULLS": "CHICAGOBULLS", "CLEVELANDCAVALIERS": "CLEVELANDCAVALIERS",
    "DALLASMAVERICKS": "DALLASMAVERICKS", "DENVERNUGGETS": "DENVERNUGGETS",
    "DETROITPISTONS": "DETROITPISTONS", "GOLDENSTATEWARRIORS": "GOLDENSTATEWARRIORS",
    "HOUSTONROCKETS": "HOUSTONROCKETS", "INDIANAPACERS": "INDIANAPACERS",
    "LACLIPPERS": "LACLIPPERS", "LALAKERS": "LALAKERS", "MEMPHISGRIZZLIES": "MEMPHISGRIZZLIES",
    "MIAMIHEAT": "MIAMIHEAT", "MILWAUKEEBUCKS": "MILWAUKEEBUCKS", "MINNESOTATIMBERWOLVES": "MINNESOTATIMBERWOLVES",
    "NEWORLEANPELICANS": "NEWORLEANPELICANS", "NYKNICKS": "NEWYORKKNICKS",
    "OKLAHOMACITYTHUNDER": "OKLAHOMACITYTHUNDER", "ORLANDOMAGIC": "ORLANDOMAGIC",
    "PHILADELPHIA76ERS": "PHILADELPHIA76ERS", "PHOENIXSUNS": "PHOENIXSUNS",
    "PORTLANDTRAILBLAZERS": "PORTLANDTRAILBLAZERS", "SACRAMENTOKINGS": "SACRAMENTOKINGS",
    "SANSANTONIOSPURS": "SANSANTONIOSPURS", "TORONTORAPTORS": "TORONTORAPTORS",
    "UTAHJAZZ": "UTAHJAZZ", "WASHINGTONWIZARDS": "WASHINGTONWIZARDS",

    # --- NHL ---
    "ANAHEIMDUCKS": "ANAHEIMDUCKS", "ARIZONACOYOTES": "ARIZONACOYOTES",
    "BOSTONBRUINS": "BOSTONBRUINS", "BUFFALOSABRES": "BUFFALOSABRES",
    "CALGARYFLAMES": "CALGARYFLAMES", "CAROLINAHURRICANES": "CAROLINAHURRICANES",
    "CHICAGOBLACKHAWKS": "CHICAGOBLACKHAWKS", "COLORADOAVALANCHE": "COLORADOAVALANCHE",
    "COLUMBUSBLUEJACKETS": "COLUMBUSBLUEJACKETS", "DALLASSTARS": "DALLASSTARS",
    "DETROITREDWINGS": "DETROITREDWINGS", "EDMONTONOILERS": "EDMONTONOILERS",
    "FLORIDAPANTHERS": "FLORIDAPANTHERS", "LOSANGELESKINGS": "LOSANGELESKINGS",
    "MINNESOTAWILD": "MINNESOTAWILD", "MONTREALCANADIENS": "MONTREALCANADIENS",
    "NASHVILLEPREDATORS": "NASHVILLEPREDATORS", "NEWJERSEYDEVILS": "NEWJERSEYDEVILS",
    "NYISLANDERS": "NYISLANDERS", "NYRANGERS": "NYRANGERS", "OTTAWASENATORS": "OTTAWASENATORS",
    "PHILADELPHIAFLYERS": "PHILADELPHIAFLYERS", "PITTSBURGH": "PITTSBURGH",
    "SANJOSESHARKS": "SANJOSESHARKS", "SEATTLEKRAKEN": "SEATTLEKRAKEN",
    "STLOUISBLUES": "STLOUISBLUES", "TAMPABAYLIGHTNING": "TAMPABAYLIGHTNING",
    "TORONTOMAPLELEAFS": "TORONTOMAPLELEAFS", "VANCOUVERCANUCKS": "VANCOUVERCANUCKS",
    "VEGASGOLDENKNIGHTS": "VEGASGOLDENKNIGHTS", "WASHINGTONCAPITALS": "WASHINGTONCAPITALS",
    "WINNIPEGJETS": "WINNIPEGJETS",

    # --- MLB ---
    "ARIZONADIAMONDBACKS": "ARIZONADIAMONDBACKS", "ATLANTABRAVES": "ATLANTABRAVES",
    "BALTIMOREORIOLES": "BALTIMOREORIOLES", "BOSTONRED": "BOSTONRED",
    "CHICAGOCUBS": "CHICAGOCUBS", "CHICAGO": "CHICAGO", "CINCINNATIREDS": "CINCINNATIREDS",
    "CLEVELANDGUARDIANS": "CLEVELANDGUARDIANS", "COLORADOROCKIES": "COLORADOROCKIES",
    "DETROITTIGERS": "DETROITTIGERS", "HOUSTONASTROS": "HOUSTONASTROS",
    "KANSASCITYROYALS": "KANSASCITYROYALS", "LAANGELS": "LAANGELS",
    "LADODGERS": "LADODGERS", "MIAMIMARLINS": "MIAMIMARLINS",
    "MILWAUKEEBREWERS": "MILWAUKEEBREWERS", "MINNESOTATWINS": "MINNESOTATWINS",
    "NYMETS": "NYMETS", "NYYANKEES": "NYYANKEES", "OAKLANDATHLETICS": "OAKLANDATHLETICS",
    "PHILADELPHIAPHILLIES": "PHILADELPHIAPHILLIES", "PITTSBURGH": "PITTSBURGH",
    "SANFRANCISCOGIANTS": "SANFRANCISCOGIANTS", "SEATTLEMARINERS": "SEATTLEMARINERS",
    "STLOUISCARDINALS": "STLOUISCARDINALS", "TAMPABAYRAYS": "TAMPABAYRAYS",
    "TEXASRANGERS": "TEXASRANGERS", "TORONTOBLUEJAYS": "TORONTOBLUEJAYS",
    "WASHINGTONNATIONALS": "WASHINGTONNATIONALS",
}

# ------------------ HELPERS ------------------ #

def safe_mean(series):
    try:
        return round(series.dropna().astype(float).mean(), 3)
    except Exception:
        return 0.0

def normalize_team(t):
    if not isinstance(t, str):
        return ""
    key = t.strip().upper().replace(" ", "").replace("-", "")
    return TEAM_MAP.get(key, key)

# ------------------ MAIN ------------------ #

def main():
    if not PRED_FILE.exists() or not STATS_FILE.exists():
        print("❌ Missing required files for learning.")
        return

    preds = pd.read_csv(PRED_FILE)
    stats = pd.read_csv(STATS_FILE)

    preds.columns = [c.strip().lower() for c in preds.columns]
    stats.columns = [c.strip().lower() for c in stats.columns]

    # Detect sport
    sport_col = "sport" if "sport" in preds.columns else None
    if sport_col:
        sports = preds[sport_col].unique()
        print(f"📊 Sports detected in predictions: {sports}")

    # Normalize prediction teams
    team_cols = [c for c in preds.columns if c in ["team1", "team2", "home", "away", "bestpick"]]
    if not team_cols:
        print(f"⚠️ No suitable team columns found in predictions file. Columns: {list(preds.columns)}")
        return
    print("✅ Using team column(s):", team_cols)
    for c in team_cols:
        preds[c + "_norm"] = preds[c].apply(normalize_team)

    # Normalize stats
    if "team" in stats.columns:
        stats["team_norm"] = stats["team"].apply(normalize_team)
    elif "home" in stats.columns:
        stats["team_norm"] = stats["home"].apply(normalize_team)
    else:
        print(f"⚠️ 'team' column missing from stats file. Columns: {list(stats.columns)}")
        return

    merged_rows = []
    for _, row in preds.iterrows():
        sport = row.get("sport", "UNKNOWN").upper()
        possible_teams = [row.get(c + "_norm", "") for c in ["team1", "team2", "home", "away", "bestpick"]]
        possible_teams = [t for t in possible_teams if t]
        for t in possible_teams:
            s = stats[stats["team_norm"] == t]
            if not s.empty:
                m = {**row.to_dict(), "sport": sport}
                for col in ["epa_off", "success_off", "epa_def", "success_def", "pace"]:
                    if col in s.columns:
                        m[col] = float(s[col].iloc[-1])
                merged_rows.append(m)
                break

    if not merged_rows:
        print("⚠️ No matching games found to merge.")
        return

    merged = pd.DataFrame(merged_rows)
    print(f"✅ Merged {len(merged)} predictions with team stat records")

    # Aggregated metrics
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

    with open(METRICS_FILE, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"🧠 Updated metrics.json with {summary['games']} merged games")

    perf = {
        "updated": summary["timestamp"],
        "combined": {
            "edge": summary["avg_edge"],
            "confidence": summary["avg_confidence"],
            "epa_off": summary["avg_epa_off"],
            "epa_def": summary["avg_epa_def"],
            "pace": summary["avg_pace"]
        },
    }

    with open(PERFORMANCE_FILE, "w") as f:
        json.dump(perf, f, indent=2)
    print("📊 performance.json written")

if __name__ == "__main__":
    main()
