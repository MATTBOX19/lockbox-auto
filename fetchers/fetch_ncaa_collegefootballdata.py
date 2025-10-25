import requests, csv, datetime as dt, time
from collections import defaultdict

BASE = "https://api.collegefootballdata.com"

def fetch_team_stats(year=2024):
    url = f"{BASE}/games?year={year}&seasonType=regular"
    r = requests.get(url, timeout=20)
    data = r.json()
    stats = defaultdict(lambda: {"points_for":0, "points_against":0, "games_played":0})
    for g in data:
        if g.get("home_points") is None: continue
        home, away = g["home_team"], g["away_team"]
        stats[home]["points_for"] += g["home_points"]
        stats[home]["points_against"] += g["away_points"]
        stats[home]["games_played"] += 1
        stats[away]["points_for"] += g["away_points"]
        stats[away]["points_against"] += g["home_points"]
        stats[away]["games_played"] += 1
        time.sleep(0.005)
    rows = []
    now = dt.datetime.utcnow().isoformat() + "Z"
    for t,v in stats.items():
        v.update({"team": t, "sport": "NCAAF", "updated_at": now})
        rows.append(v)
    return rows

def write_csv(rows, path):
    if not rows: return
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader(); w.writerows(rows)

if __name__ == "__main__":
    rows = fetch_team_stats()
    write_csv(rows, "Data/ncaaf_team_stats_free.csv")
    print(f"Saved NCAAF: {len(rows)} rows → Data/ncaaf_team_stats_free.csv")
