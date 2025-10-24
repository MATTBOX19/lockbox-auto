#!/usr/bin/env python3
"""
lockbox_learn_stats.py — Combine LockBox predictions with SportsData.io stats

Purpose:
  • Merge AI predictions with real game + stat data.
  • Learn which team-level metrics correlate with outcomes.
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


def safe_mean(series):
    try:
        return round(series.dropna().astype(float).mean(), 3)
    except Exception:
        return 0.0


def normalize_team(t):
    if not isinstance(t, str):
        return ""
    return t.strip().upper().replace(" ", "").replace("-", "")


def main():
    if not PRED_FILE.exists() or not STATS_FILE.exists():
        print("❌ Missing required files for learning.")
        return

    preds = pd.read_csv(PRED_FILE)
    stats = pd.read_csv(STATS_FILE)

    preds.columns = [c.strip() for c in preds.columns]
    stats.columns = [c.strip() for c in stats.columns]

    # --- Normalize team names ---
    if "BestPick" in preds.columns:
        preds["Team1_norm"] = preds["BestPick"].apply(normalize_team)
        preds["Team2_norm"] = ""  # optional placeholder
        print("✅ Using BestPick column as team identifier.")
    elif "Team" in preds.columns:
        preds["Team1_norm"] = preds["Team"].apply(normalize_team)
        preds["Team2_norm"] = ""
        print("✅ Using Team column as team identifier.")
    else:
        print(f"⚠️ No suitable team column found in predictions file. Columns: {preds.columns.tolist()}")
        return

    # --- Normalize stats team names ---
    if "team" in stats.columns:
        stats["team_norm"] = stats["team"].apply(normalize_team)
    elif "Home" in stats.columns:
        stats["team_norm"] = stats["Home"].apply(normalize_team)
    elif "Team" in stats.columns:
        stats["team_norm"] = stats["Team"].apply(normalize_team)
    else:
        print(f"⚠️ No team column found in stats file. Columns: {stats.columns.tolist()}")
        return

    merged_rows = []
    for _, row in preds.iterrows():
        t1 = row["Team1_norm"]
        s1 = stats[stats["team_norm"] == t1].tail(1)
        if not s1.empty:
            m = {**row.to_dict()}
            for col in ["HomeYards", "AwayYards", "HomeTurnovers", "AwayTurnovers",
                        "HomePossession", "HomeScore", "AwayScore"]:
                if col in s1.columns:
                    m[col] = float(s1[col].iloc[0]) if pd.notna(s1[col].iloc[0]) else 0
            merged_rows.append(m)

    if not merged_rows:
        print("⚠️ No matching games found to merge.")
        return

    merged = pd.DataFrame(merged_rows)
    print(f"✅ Merged {len(merged)} prediction rows with stat records")

    # --- Summaries ---
    if "Edge" in merged.columns:
        merged["Edge"] = pd.to_numeric(merged["Edge"], errors="coerce")
        merged["Confidence"] = pd.to_numeric(merged.get("Confidence", 0), errors="coerce")

    summary = {
        "timestamp": datetime.utcnow().isoformat(),
        "games": len(merged),
        "avg_edge": safe_mean(merged["Edge"]),
        "avg_confidence": safe_mean(merged["Confidence"]),
        "avg_home_yards": safe_mean(merged.get("HomeYards", pd.Series(dtype=float))),
        "avg_away_yards": safe_mean(merged.get("AwayYards", pd.Series(dtype=float))),
        "avg_turnovers_diff": safe_mean(merged.get("HomeTurnovers", pd.Series(dtype=float)))
            - safe_mean(merged.get("AwayTurnovers", pd.Series(dtype=float))),
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
