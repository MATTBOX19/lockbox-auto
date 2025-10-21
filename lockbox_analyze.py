#!/usr/bin/env python3
"""
lockbox_analyze.py

Phase 5: Advanced AI Analysis Core (Experimental)

Purpose:
  - Adds deeper model context from line movement, injuries, weather,
    EPA/success-rate blends, and recent team form.
  - Designed to evolve LockBox from a static predictor into a
    self-tuning model that learns from performance data.

Outputs:
  /Output/Analyze_Report.csv

NOTE:
  This initial version uses simulated metrics & placeholders.
  Future integration will connect real APIs (NFLWeather, PBWR,
  team EPA data, and line-movement feeds).
"""

import pandas as pd
from pathlib import Path
from datetime import datetime
import random

ROOT = Path(".")
OUT_DIR = ROOT / "Output"
OUT_DIR.mkdir(exist_ok=True)

def load_latest_predictions():
    files = sorted(OUT_DIR.glob("Predictions_*_Explained.csv"))
    if not files:
        print("⚠️ No predictions found.")
        return None
    return files[-1]

def mock_team_metrics(team):
    """Simulate metrics until real APIs are wired."""
    return {
        "EPA_rank": random.randint(1, 32),
        "SuccessRate_rank": random.randint(1, 32),
        "PassBlock_rank": random.randint(1, 32),
        "DefPressure_rank": random.randint(1, 32),
        "ExplosiveRate_rank": random.randint(1, 32),
        "InjuryImpact": round(random.uniform(-2, 2), 2),
        "WeatherAdj": round(random.uniform(-1, 1), 2)
    }

def analyze_predictions(pred_file: Path):
    df = pd.read_csv(pred_file)
    df.columns = [c.strip() for c in df.columns]

    analysis_rows = []
    for _, row in df.iterrows():
        team1, team2 = row.get("Team1", ""), row.get("Team2", "")
        pick = row.get("MoneylinePick", "")
        edge = float(row.get("Edge", 0))
        conf = float(row.get("Confidence", 0))

        m1 = mock_team_metrics(team1)
        m2 = mock_team_metrics(team2)

        # Compute matchup delta (lower rank = better)
        epa_diff = m2["EPA_rank"] - m1["EPA_rank"]
        sr_diff = m2["SuccessRate_rank"] - m1["SuccessRate_rank"]

        tech_edge = round((epa_diff + sr_diff) / 64.0, 2)
        injury_signal = m1["InjuryImpact"] - m2["InjuryImpact"]
        weather_signal = m1["WeatherAdj"] + m2["WeatherAdj"]

        adj_edge = round(edge + tech_edge + (injury_signal * 0.1) + (weather_signal * 0.05), 2)
        adj_conf = round(min(100, max(0, conf + adj_edge * 5)), 2)

        analysis_rows.append({
            "Sport": row.get("Sport", ""),
            "Teams": f"{team1} vs {team2}",
            "Pick": pick,
            "OrigEdge": edge,
            "AdjEdge": adj_edge,
            "OrigConf": conf,
            "AdjConf": adj_conf,
            "EPA_Diff": epa_diff,
            "SR_Diff": sr_diff,
            "InjurySignal": injury_signal,
            "WeatherSignal": weather_signal
        })

    out_df = pd.DataFrame(analysis_rows)
    out_path = OUT_DIR / f"Analyze_Report_{datetime.utcnow().strftime('%Y-%m-%d')}.csv"
    out_df.to_csv(out_path, index=False)
    print(f"✅ Analyze report created: {out_path} ({len(out_df)} rows)")

if __name__ == "__main__":
    latest = load_latest_predictions()
    if latest:
        print(f"Analyzing {latest.name} ...")
        analyze_predictions(latest)
    else:
        print("❌ No predictions to analyze.")
