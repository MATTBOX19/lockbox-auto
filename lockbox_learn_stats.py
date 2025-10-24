#!/usr/bin/env python3
"""
lockbox_learn_stats.py — Merge LockBox predictions with SportsData.io stats (NFL/NBA/NHL/MLB)

Purpose:
  • Merge AI picks with SportsData.io team stats.
  • Normalize team names automatically.
  • Update metrics.json and performance.json for dashboard.
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

# --- Common team name aliases ---
TEAM_MAP = {
    # NFL
    "VIKINGS": "MIN", "CHARGERS": "LAC", "COWBOYS": "DAL", "EAGLES": "PHI", "CHIEFS": "KC",
    "BILLS": "BUF", "PACKERS": "GB", "JETS": "NYJ", "GIANTS": "NYG", "BEARS": "CHI",
    "LIONS": "DET", "DOLPHINS": "MIA", "PATRIOTS": "NE", "RAIDERS": "LV", "BRONCOS": "DEN",
    "RAVENS": "BAL", "BENGALS": "CIN", "STEELERS": "PIT", "TEXANS": "HOU", "COLTS": "IND",
    "TITANS": "TEN", "SAINTS": "NO", "FALCONS": "ATL", "BUCCANEERS": "TB", "JAGUARS": "JAX",
    "COMMANDERS": "WSH", "49ERS": "SF", "SEAHAWKS": "SEA", "CARDINALS": "ARI", "RAMS": "LAR",
    "PANTHERS": "CAR",
    # NBA
    "LAKERS": "LAL", "CELTICS": "BOS", "WARRIORS": "GSW", "BULLS": "CHI", "MAVERICKS": "DAL",
    "NUGGETS": "DEN", "BUCKS": "MIL", "SUNS": "PHX", "NETS": "BKN",
    # NHL
    "MAPLELEAFS": "TOR", "BRUINS": "BOS", "RANGERS": "NYR", "KRAKEN": "SEA",
    # MLB
    "YANKEES": "NYY", "REDSOX": "BOS", "DODGERS": "LAD", "BRAVES": "ATL",
}

def normalize_team(name: str) -> str:
    if not isinstance(name, str) or not name.strip():
        return ""
    t = name.upper().replace(" ", "").replace("-", "").replace(".", "")
    for key, abbr in TEAM_MAP.items():
        if key in t:
            return abbr
    return t[:3]

def safe_mean(series):
    try:
        return round(series.dropna().astype(float).mean(), 3)
    except Exception:
        return 0.0

def main():
    if not PRED_FILE.exists() or not STATS_FILE.exists():
        print("❌ Missing required files for learning.")
        return

    preds = pd.read_csv(PRED_FILE)
    stats = pd.read_csv(STATS_FILE)
    preds.columns = [c.strip() for c in preds.columns]
    stats.columns = [c.strip() for c in stats.columns]

    # --- Normalize teams from BestPick ---
    if "BestPick" in preds.columns:
        preds["Team1_norm"] = preds["BestPick"].apply(normalize_team)
        print("✅ Using BestPick column as team identifier.")
    else:
        print("⚠️ No BestPick column found in predictions file.")
        return

    # --- Normalize team names in stats dynamically ---
    lower_cols = [c.lower() for c in stats.columns]
    def norm_col(colname):
        return colname if colname in stats.columns else next((c for c in stats.columns if c.lower() == colname.lower()), None)

    home_col = norm_col("Home")
    away_col = norm_col("Away")
    winner_col = norm_col("Winner")

    if home_col:
        stats["Home_norm"] = stats[home_col].apply(normalize_team)
    if away_col:
        stats["Away_norm"] = stats[away_col].apply(normalize_team)
    if winner_col:
        stats["Winner_norm"] = stats[winner_col].apply(normalize_team)

    if not any(col in stats.columns for col in ["Home_norm", "Away_norm", "Winner_norm"]):
        print(f"⚠️ Could not find home/away/winner columns in stats file. Columns: {stats.columns.tolist()}")
        return

    merged_rows = []
    for _, row in preds.iterrows():
        t = row["Team1_norm"]
        mask = pd.Series([False] * len(stats))
        for col in ["Home_norm", "Away_norm", "Winner_norm"]:
            if col in stats.columns:
                mask |= stats[col] == t
        s = stats[mask]
        if not s.empty:
            latest = s.tail(1)
            m = {**row.to_dict()}
            for col in ["HomeScore", "AwayScore", "HomeYards", "AwayYards",
                        "HomeTurnovers", "AwayTurnovers", "HomePossession", "AwayPossession"]:
                if col in latest.columns:
                    m[col] = float(latest[col].iloc[0]) if pd.notna(latest[col].iloc[0]) else 0
            merged_rows.append(m)

    if not merged_rows:
        print("⚠️ No matching games found to merge.")
        return

    merged = pd.DataFrame(merged_rows)
    print(f"✅ Merged {len(merged)} predictions with stat records")

    merged["Edge"] = pd.to_numeric(merged.get("Edge", 0), errors="coerce")
    merged["Confidence"] = pd.to_numeric(merged.get("Confidence", 0), errors="coerce")

    summary = {
        "timestamp": datetime.utcnow().isoformat(),
        "games": len(merged),
        "avg_edge": safe_mean(merged["Edge"]),
        "avg_confidence": safe_mean(merged["Confidence"]),
        "avg_home_yards": safe_mean(merged.get("HomeYards", pd.Series(dtype=float))),
        "avg_away_yards": safe_mean(merged.get("AwayYards", pd.Series(dtype=float))),
        "avg_turnovers_diff": safe_mean(merged.get("HomeTurnovers", pd.Series(dtype=float))) -
                              safe_mean(merged.get("AwayTurnovers", pd.Series(dtype=float))),
    }

    with open(METRICS_FILE, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"🧠 Updated metrics.json with {summary['games']} merged games")

    perf = {
        "updated": summary["timestamp"],
        "NFL": {
            "edge": summary["avg_edge"],
            "confidence": summary["avg_confidence"],
            "yards_diff": summary["avg_home_yards"] - summary["avg_away_yards"],
        },
    }
    with open(PERFORMANCE_FILE, "w") as f:
        json.dump(perf, f, indent=2)
    print("📊 performance.json written")


if __name__ == "__main__":
    main()
