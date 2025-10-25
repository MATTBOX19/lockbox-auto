import csv, datetime as dt, time, json, urllib.request
from collections import defaultdict

BASE = "https://statsapi.mlb.com/api/v1"

def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "lockbox-auto/1.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode())

def fetch_team_stats(start_date: str, end_date: str):
    start = dt.date.fromisoformat(start_date)
    end = dt.date.fromisoformat(end_date)
    delta = dt.timedelta(days=1)
    games = []
    d = start
    while d <= end:
        data = _get(f"{BASE}/schedule?sportId=1&date={d}")
        for date_data in data.get("dates", []):
            for g in date_data.get("games", []):
                if g.get("gamePk"): games.append(g["gamePk"])
        d += delta; time.sleep(0.05)

    agg = defaultdict(lambda: defaultdict(float))
    gp = defaultdict(int)
    for gid in games:
        try:
            box = _get(f"{BASE}/game/{gid}/boxscore")
        except Exception:
            continue
        teams = box.get("teams", {})
        for side in ("home", "away"):
            t = teams.get(side, {})
            team = t.get("team", {}).get("abbreviation") or t.get("team", {}).get("name")
            stats = t.get("teamStats", {}).get("batting", {}) or {}
            if not team: continue
            a = agg[team]
            a["runs"] += stats.get("runs", 0)
            a["hits"] += stats.get("hits", 0)
            a["home_runs"] += stats.get("homeRuns", 0)
            gp[team] += 1
        time.sleep(0.05)

    rows = []
    now = dt.datetime.utcnow().isoformat() + "Z"
    for team, s in agg.items():
        rows.append({
            "sport": "MLB",
            "team": team,
            "games_played": gp[team],
            "runs": s["runs"],
            "hits": s["hits"],
            "home_runs": s["home_runs"],
            "updated_at": now
        })
    return rows

def write_csv(rows, path):
    if not rows: return
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader(); w.writerows(rows)

if __name__ == "__main__":
    today = dt.date.today()
    start = dt.date(today.year, 3, 1)
    rows = fetch_team_stats(start.isoformat(), today.isoformat())
    write_csv(rows, "Data/mlb_team_stats_free.csv")
    print(f"Saved MLB: {len(rows)} rows → Data/mlb_team_stats_free.csv")
