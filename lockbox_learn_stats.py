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

    # --- Match prediction team columns ---
    team_cols = [c for c in preds.columns if any(k in c.lower() for k in ["team", "home", "away", "matchup", "pick"])]
    if len(team_cols) >= 2:
        preds["Team1_norm"] = preds[team_cols[0]].apply(normalize_team)
        preds["Team2_norm"] = preds[team_cols[1]].apply(normalize_team)
        print(f"✅ Using prediction team columns: {team_cols[0]} / {team_cols[1]}")
    else:
        print(f"⚠️ No suitable team columns found in predictions file. Columns: {preds.columns.tolist()}")
        return

    # --- Stats side normalization ---
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
        t2 = row["Team2_norm"]
        s1 = stats[stats["team_norm"] == t1].tail(1)
        s2 = stats[stats["team_norm"] == t2].tail(1)
        if not s1.empty and not s2.empty:
            m = {**row.to_dict()}
            for prefix, df in zip(["T1_", "T2_"], [s1, s2]):
                for col in ["HomeYards", "AwayYards", "HomeTurnovers", "AwayTurnovers", "HomePossession", "HomeScore", "AwayScore"]:
                    if col in df.columns:
                        m[prefix + col] = float(df[col].iloc[0]) if pd.notna(df[col].iloc[0]) else 0
            merged_rows.append(m)

    if not merged_rows:
        print("⚠️ No matching games found to merge.")
        return

    merged = pd.DataFrame(merged_rows)
    print(f"✅ Merged {len(merged)} prediction rows with stat records")

    if "Edge" in merged.columns:
        merged["Edge"] = pd.to_numeric(merged["Edge"], errors="coerce")
        merged["Confidence"] = pd.to_numeric(merged.get("Confidence", 0), errors="coerce")

    summary = {
        "timestamp": datetime.utcnow().isoformat(),
        "games": len(merged),
        "avg_edge": safe_mean(merged["Edge"]),
        "avg_confidence": safe_mean(merged["Confidence"]),
        "avg_home_yards": safe_mean(merged.filter(like="HomeYards")),
        "avg_away_yards": safe_mean(merged.filter(like="AwayYards")),
        "avg_turnovers_diff": safe_mean(merged.filter(like="HomeTurnovers"))
            - safe_mean(merged.filter(like="AwayTurnovers")),
    }

    with open(METRICS_FILE, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"🧠 Updated metrics.json with {summary['games']} merged games")

    perf = {
        "updated": summary["timestamp"],
        "NFL": {
            "edge": summary["avg_edge"],
            "confidence": summary["avg_confidence"],
            "yards_diff": summary["avg_home_yards"] - summary["avg_away_yards"]
        },
    }
    with open(PERFORMANCE_FILE, "w") as f:
        json.dump(perf, f, indent=2)
    print("📊 performance.json written")

if __name__ == "__main__":
    main()
