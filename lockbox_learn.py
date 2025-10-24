#!/usr/bin/env python3
"""
lockbox_learn.py — LockBox Adaptive Learning (Pro Version)

Purpose:
  • Reads the most recent Settled CSV.
  • Computes model accuracy & ROI overall and by sport.
  • Updates rolling metrics.json (history of sessions).
  • Writes per-sport summary to performance.json for dashboard use.
  • Automatically refreshes Predictions_latest_Explained.csv for website.

Outputs:
  /Output/metrics.json
  /Output/performance.json
  /Output/Predictions_latest_Explained.csv
"""

import pandas as pd, json, shutil
from pathlib import Path
from datetime import datetime

ROOT = Path(".")
OUT_DIR = ROOT / "Output"
METRICS_FILE = OUT_DIR / "metrics.json"
PERFORMANCE_FILE = OUT_DIR / "performance.json"


def find_latest_settled():
    files = sorted(OUT_DIR.glob("Predictions_*_Settled.csv"))
    if not files:
        print("⚠️ No settled files found.")
        return None
    return files[-1]


def safe_mean(series):
    return round(series.dropna().astype(float).mean(), 3) if not series.empty else 0


def analyze_settled(file: Path):
    df = pd.read_csv(file)
    df.columns = [c.strip() for c in df.columns]
    if "Settled" not in df.columns:
        print("⚠️ No Settled column — skipping.")
        return None

    settled = df[df["Settled"].astype(str).str.lower().isin(["true", "1", "yes"])]
    if settled.empty:
        print("ℹ️ No settled rows found.")
        return None

    # --- overall stats ---
    def pct(win, total): return round((win / total) * 100, 2) if total else 0
    def roi(win, loss): return round(((win - loss) / max(1, (win + loss))) * 100, 2)

    result = {
        "timestamp": datetime.utcnow().isoformat(),
        "file": file.name,
        "games_total": len(df),
        "games_settled": len(settled),
        "avg_edge": safe_mean(df.get("Edge", pd.Series())),
        "avg_confidence": safe_mean(df.get("Confidence", pd.Series())),
    }

    # Overall win/loss counts by type
    for col in ["ML_Result", "ATS_Result", "OU_Result"]:
        if col in df.columns:
            wins = (settled[col].astype(str).str.lower() == "win").sum()
            losses = (settled[col].astype(str).str.lower() == "loss").sum()
            pushes = (settled[col].astype(str).str.lower() == "push").sum()
            t = col.split("_")[0].lower()
            result[f"{t}_wins"] = int(wins)
            result[f"{t}_losses"] = int(losses)
            result[f"{t}_pushes"] = int(pushes)
            result[f"{t}_win_pct"] = pct(wins, wins + losses)
            result[f"{t}_roi_percent"] = roi(wins, losses)

    # --- per-sport metrics ---
    per_sport = {}
    if "Sport" in df.columns:
        for sport, grp in settled.groupby("Sport"):
            sport_data = {}
            for col in ["ML_Result", "ATS_Result", "OU_Result"]:
                if col in grp.columns:
                    w = (grp[col].astype(str).str.lower() == "win").sum()
                    l = (grp[col].astype(str).str.lower() == "loss").sum()
                    sport_data[col.replace("_Result", "")] = {
                        "win_pct": pct(w, w + l),
                        "roi": roi(w, l),
                    }
            per_sport[sport] = sport_data

    result["per_sport"] = per_sport
    print(f"✅ Learned from {len(settled)} games — overall Win%={result.get('ml_win_pct',0)} | ATS={result.get('ats_win_pct',0)} | OU={result.get('ou_win_pct',0)}")
    return result


def update_metrics(new_data):
    """Append to rolling metrics.json (max 30 sessions)"""
    if not new_data:
        return
    metrics = []
    if METRICS_FILE.exists():
        try:
            metrics = json.load(open(METRICS_FILE))
            if not isinstance(metrics, list):
                metrics = [metrics]
        except:
            metrics = []
    metrics.append(new_data)
    with open(METRICS_FILE, "w") as f:
        json.dump(metrics[-30:], f, indent=2)
    print(f"🧠 metrics.json updated ({len(metrics[-30:])} sessions kept)")

    # also write performance.json snapshot
    per = new_data.get("per_sport", {})
    perf = {"updated": new_data["timestamp"]}
    for sport, stats in per.items():
        perf[sport] = {k: v for k, v in stats.items()}
    with open(PERFORMANCE_FILE, "w") as f:
        json.dump(perf, f, indent=2)
    print(f"📊 performance.json written ({len(per)} sports)")


if __name__ == "__main__":
    latest = find_latest_settled()
    if latest:
        res = analyze_settled(latest)
        if res:
            update_metrics(res)

            # 🔄 Update website file so Flask dashboard shows newest data
            try:
                target = OUT_DIR / "Predictions_latest_Explained.csv"
                shutil.copy(latest, target)
                print(f"🌐 Updated {target.name} for website display")
            except Exception as e:
                print(f"⚠️ Failed to update website file: {e}")
    else:
        print("❌ No settled data available.")
