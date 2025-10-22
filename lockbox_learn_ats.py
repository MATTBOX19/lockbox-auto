#!/usr/bin/env python3
"""
lockbox_learn_ats.py — Phase 7: ATS statistical learner for LockBox
Uses settled history to learn which teams/edge bands cover most often.
Outputs: /Output/learn_weights.json
"""

import os, json, pandas as pd
from pathlib import Path
from datetime import datetime

ROOT = Path(".")
OUT_DIR = ROOT / "Output"
HISTORY_FILE = OUT_DIR / "history.csv"
LEARN_FILE = OUT_DIR / "learn_weights.json"

def load_history():
    if not HISTORY_FILE.exists():
        print("❌ No history.csv found — nothing to learn yet.")
        return pd.DataFrame()
    try:
        df = pd.read_csv(HISTORY_FILE)
        needed = {"team1","ats","edge","settled","result"}
        if not needed.issubset(df.columns):
            print("⚠️ history.csv missing columns; learner skipped.")
            return pd.DataFrame()
        df = df[df["settled"] == True]
        df = df[df["result"].isin(["win","loss","push"])]
        return df
    except Exception as e:
        print("⚠️ Failed to load history:", e)
        return pd.DataFrame()

def compute_ats_learning(df):
    if df.empty:
        return {}

    # bucket edge ranges
    bins  = [0,2,4,6,8,10,20,50]
    labels = ["0-2","2-4","4-6","6-8","8-10","10-20","20+"]
    df["edge_band"] = pd.cut(df["edge"], bins=bins, labels=labels, right=False)

    df = df[df["ats"].notna() & (df["ats"] != "")]
    if df.empty:
        return {}

    # numeric scores: win=1, push=0.5, loss=0
    df["score"] = df["result"].map({"win":1,"push":0.5,"loss":0})
    summary = (
        df.groupby(["team1","edge_band"])["score"]
        .mean()
        .reset_index()
        .rename(columns={"score":"win_rate"})
    )

    learn = {}
    for _,r in summary.iterrows():
        learn.setdefault(r["team1"],{})[r["edge_band"]] = round(float(r["win_rate"]),3)
    return learn

def update_weights(new_data):
    if not new_data:
        print("ℹ️ No new ATS learning data.")
        return
    old = {}
    if LEARN_FILE.exists():
        try: old = json.load(open(LEARN_FILE))
        except: pass
    for team,bands in new_data.items():
        for band,val in bands.items():
            old_val = old.get(team,{}).get(band,val)
            blended = round(0.7*old_val + 0.3*val,3)
            old.setdefault(team,{})[band] = blended
    old["_meta"] = {"updated":datetime.utcnow().isoformat()}
    json.dump(old, open(LEARN_FILE,"w"), indent=2)
    print(f"✅ Updated ATS learn_weights.json with {len(new_data)} teams")

def main():
    df = load_history()
    new = compute_ats_learning(df)
    update_weights(new)

if __name__=="__main__":
    main()
