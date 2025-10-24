#!/usr/bin/env python3
"""
lockbox_learn_stats.py — Merge LockBox predictions with SportsData.io team stats

Purpose:
  • Join LockBox picks with single-team stat data (EPA, success, pace, etc.)
  • Normalize team names and compute averages.
  • Update metrics.json and performance.json for dashboard display.
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

# --- TEAM MAP (for normalization) ---
TEAM_MAP = {
    "VIKINGS": "MIN", "CHARGERS": "LAC", "COWBOYS": "DAL", "EAGLES": "PHI", "CHIEFS": "KC",
    "BILLS": "BUF", "PACKERS": "GB", "JETS": "NYJ", "GIANTS": "NYG", "BEARS": "CHI",
    "LIONS": "DET", "DOLPHINS": "MIA", "PATRIOTS": "NE", "RAIDERS": "LV", "BRONCOS": "DEN",
    "RAVENS": "BAL", "BENGALS": "CIN", "STEELERS": "PIT", "TEXANS": "HOU", "COLTS": "IND",
    "TITANS": "TEN", "SAINTS": "NO", "FALCONS": "ATL", "BUCCANEERS": "TB", "JAGUARS": "JAX",
    "COMMANDERS": "WSH", "49ERS": "SF", "SEAHAWKS": "SEA", "CARDINALS": "ARI", "RAMS": "LAR",
    "PANTHERS": "CAR",
}

def normalize_team(name: str) -> str:
    if not isinstance(name, str) or not name.strip():
        return ""
    t = name.upper().replace(" ", "").replace("-", "")
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
    stats.columns = [c.strip().lower() for c in stats.columns]

    # --- Normalize predictions ---
    if "BestPick" in preds.columns:
        preds["team_norm"] = preds["BestPick"].apply(normalize_team)
        print("✅ Using BestPick column as team identifier.")
    else:
        print("⚠️ No BestPick column found in predictions file.")
        return

    # --- Normalize stats ---
    if "team" not in stats.columns:
        print(f"⚠️ 'team' column missing from stats file. Columns: {stats.columns.tolist()}")
        return
    stats["team_norm"] = stats["team"].apply(normalize_team)

    # --- Merge predictions with stats ---
    merged = preds.merge(stats, how="left", left_on="team_norm", right_on="team_norm")
    if merged.empty:
        print("⚠️ No matching teams found to merge.")
        return

    print(f"✅ Merged {len(merged)} predictions with team stat records")

    merged["Edge"] = pd.to_numeric(merged.get("Edge", 0), errors="coerce")
    merged["Confidence"] = pd.to_numeric(merged.get("Confidence", 0), errors="coerce")

    summary = {
        "timestamp": datetime.utcnow().isoformat(),
        "games": len(merged),
        "avg_edge": safe_mean(merged["Edge"]),
        "avg_confidence": safe_mean(merged["Confidence"]),
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
        "NFL": {
            "edge": summary["avg_edge"],
            "confidence": summary["avg_confidence"],
            "epa_diff": summary["avg_epa_off"] - summary["avg_epa_def"],
            "success_diff": summary["avg_success_off"] - summary["avg_success_def"],
            "pace": summary["avg_pace"],
        },
    }
    with open(PERFORMANCE_FILE, "w") as f:
        json.dump(perf, f, indent=2)
    print("📊 performance.json written")

if __name__ == "__main__":
    main()
