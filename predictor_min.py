#!/usr/bin/env python3
"""
predictor_min.py — minimal, reliable generator for LockBox.
- Pulls odds (ML, spreads, totals) from The Odds API
- Produces Output/Predictions_latest_Explained.csv
- No heavy modeling (fast start); computes a simple pick + confidence + edge
"""
import os, json, time, math, requests, pandas as pd
from pathlib import Path
from datetime import datetime, timezone

ODDS_API_KEY = os.getenv("ODDS_API_KEY", "")
REGION = "us"
MARKETS = "h2h,spreads,totals"
SPORTS = [
    "americanfootball_nfl",
    "americanfootball_ncaaf",
    "basketball_nba",
    "icehockey_nhl",
    "baseball_mlb",
]

ROOT = Path(".")
OUT_DIR = Path(os.getenv("OUTPUT_DIR", ROOT / "Output"))
OUT_DIR.mkdir(parents=True, exist_ok=True)
LATEST = OUT_DIR / "Predictions_latest_Explained.csv"

def implied_prob(odds_american: int) -> float:
    o = int(odds_american)
    if o > 0:  # +150
        return 100.0 / (o + 100.0)
    else:     # -150
        return (-o) / ((-o) + 100.0)

def fair_prob(p1, p2):
    s = p1 + p2
    return (p1/s, p2/s) if s > 0 else (0.5, 0.5)

def fetch_events(sport):
    url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds"
    params = {"regions": REGION, "markets": MARKETS, "oddsFormat": "american", "apiKey": ODDS_API_KEY}
    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()
    return r.json()

def best_price(prices):
    # Pick one book’s odds. For simplicity: best ML, best spread (home/away), best total.
    # prices is a list of bookmaker dicts.
    best = {"ml": {}, "spread": {}, "total": {}}
    for b in prices:
        for mk in b.get("markets", []):
            key = mk.get("key")
            for o in mk.get("outcomes", []):
                name = o.get("name","")
                price = o.get("price")
                if price is None: continue
                if key == "h2h":
                    if name not in best["ml"] or abs(price) > abs(best["ml"][name]):
                        best["ml"][name] = int(price)
                elif key == "spreads":
                    pt = o.get("point")
                    cur = best["spread"].get(name)
                    if cur is None or abs(price) > abs(cur["price"]):
                        best["spread"][name] = {"price": int(price), "point": float(pt)}
                elif key == "totals":
                    pt = o.get("point")
                    cur = best["total"].get(name)
                    if cur is None or abs(price) > abs(cur["price"]):
                        best["total"][name] = {"price": int(price), "point": float(pt)}
    return best

rows = []
for sport in SPORTS:
    try:
        data = fetch_events(sport)
    except Exception as e:
        print(f"⚠️ {sport} fetch failed: {e}")
        continue

    for ev in data:
        teams = ev.get("teams") or []
        if len(teams) != 2:
            continue
        team1, team2 = teams[0], teams[1]
        commence = ev.get("commence_time","")
        prices = best_price(ev.get("bookmakers", []))

        # Moneyline pick
        ml1 = prices["ml"].get(team1); ml2 = prices["ml"].get(team2)
        ml_text = ""
        if ml1 is not None and ml2 is not None:
            p1 = implied_prob(ml1); p2 = implied_prob(ml2)
            p1, p2 = fair_prob(p1, p2)
            pick_ml = team1 if p1 >= p2 else team2
            conf_ml = round(100.0 * max(p1, p2), 1)
            edge_ml = round(abs(p1 - 0.5), 3)  # simple edge vs coinflip
            ml_text = f"{team1}:{ml1} | {team2}:{ml2}"
        else:
            pick_ml, conf_ml, edge_ml = ("", 0.0, 0.0)

        # ATS (pick team with line advantage if spreads exist)
        ats_text = ""
        s1 = prices["spread"].get(team1); s2 = prices["spread"].get(team2)
        if s1 and s2:
            # crude approach: prefer side with shorter price at same (or better) point
            # if line points differ, adjust by 0.5 per point
            val1 = (abs(s1["price"]) / 100.0) - (s1["point"] / 2.0)
            val2 = (abs(s2["price"]) / 100.0) - (s2["point"] / 2.0)
            pick_ats = f"{team1} {s1['point']:+g}" if val1 <= val2 else f"{team2} {s2['point']:+g}"
            edge_ats = round(abs(val2 - val1), 3)
            ats_text = f"{team1}:{s1['price']}({s1['point']:+g}) | {team2}:{s2['price']}({s2['point']:+g})"
        else:
            pick_ats, edge_ats = ("", 0.0)

        # Totals (lean toward side with better price)
        ou_text = ""
        t_over = prices["total"].get("Over"); t_under = prices["total"].get("Under")
        if t_over and t_under and abs(t_over["point"] - t_under["point"]) < 1e-6:
            pick_ou = "Over" if abs(t_over["price"]) < abs(t_under["price"]) else "Under"
            ou_pt = t_over["point"]
            ou_text = f"Over:{t_over['price']} / Under:{t_under['price']} @ {ou_pt}"
        else:
            pick_ou = ""

        reason = "Market-based baseline (quick start). Improves as we add stats."
        rows.append({
            "Sport": sport.split("_")[-1].upper() if "_" in sport else sport.upper(),
            "GameTime": commence,
            "Team1": team1,
            "Team2": team2,
            "MoneylinePick": pick_ml,
            "Confidence": conf_ml,
            "Edge": edge_ml,
            "ML": ml_text,
            "ATS": ats_text,
            "OU": ou_text,
            "Reason": reason,
            "LockEmoji": "🔒" if edge_ml >= 0.5 and conf_ml >= 60 else "",
            "UpsetEmoji": "⚠️" if edge_ml >= 0.3 and conf_ml < 55 else "",
        })

df = pd.DataFrame(rows, columns=[
    "Sport","GameTime","Team1","Team2","MoneylinePick","Confidence","Edge","ML","ATS","OU","Reason","LockEmoji","UpsetEmoji"
])
df.to_csv(LATEST, index=False)
dated = OUT_DIR / f"Predictions_{datetime.now(timezone.utc).strftime('%Y-%m-%d')}_Explained.csv"
df.to_csv(dated, index=False)
print(f"✅ Wrote {LATEST} and {dated} with {len(df)} rows.")
