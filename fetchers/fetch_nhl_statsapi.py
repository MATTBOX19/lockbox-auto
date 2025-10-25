from __future__ import annotations
import csv, datetime as dt, time, json, urllib.request
from collections import defaultdict
from typing import Dict, Any, List

BASE = "https://statsapi.web.nhl.com/api/v1"

def _get(url: str) -> Dict[str, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": "lockbox-auto/1.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))

def fetch_team_stats(start_date: str, end_date: str) -> List[Dict[str, Any]]:
    start = dt.date.fromisoformat(start_date)
    end = dt.date.fromisoformat(end_date)
    chunk = dt.timedelta(days=7)
    game_ids = []
    d0 = start
    while d0 <= end:
        d1 = min(d0 + chunk, end)
        data = _get(f"{BASE}/schedule?startDate={d0}&endDate={d1}")
        for day in data.get("dates", []):
            for g in day.get("games", []):
                game_ids.append(g["gamePk"])
        d0 = d1 + dt.timedelta(days=1)
        time.sleep(0.15)

    agg = defaultdict(lambda: defaultdict(float))
    games_played = defaultdict(int)
    for gid in game_ids:
        try:
            box = _get(f"{BASE}/game/{gid}/boxscore")
        except Exception:
            continue
        teams = box.get("teams", {})
        for side in ("home", "away"):
            t = teams.get(side, {})
            team = (
                t.get("team", {}).get("triCode")
                or t.get("team", {}).get("abbreviation")
                or t.get("team", {}).get("name")
            )
            stats = t.get("teamStats", {}).get("teamSkaterStats", {}) or {}
            opp_side = "away" if side == "home" else "home"
            opp_stats = teams.get(opp_side, {}).get("teamStats", {}).get("teamSkaterStats", {}) or {}
            if not team:
                continue
            a = agg[team]
            a["goals_for"] += float(stats.get("goals", 0))
            a["goals_against"] += float(opp_stats.get("goals", 0))
            a["shots_for"] += float(stats.get("shots", 0))
            a["shots_against"] += float(opp_stats.get("shots", 0))
            games_played[team] += 1
        time.sleep(0.1)

    rows = []
    now = dt.datetime.utcnow().isoformat() + "Z"
    for team, a in agg.items():
        gp = games_played[team]
        rows.append({
            "sport": "NHL",
            "team": team,
            "games_played": gp,
            "goals_for": a["goals_for"],
            "goals_against": a["goals_against"],
            "shots_for": a["shots_for"],
            "shots_against": a["shots_against"],
            "updated_at": now,
        })
    return rows

def write_csv(rows, path):
    if not rows:
        return
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

if __name__ == "__main__":
    today = dt.date.today()
    start = dt.date(today.year, 9, 15)
    rows = fetch_team_stats(start.isoformat(), today.isoformat())
    write_csv(rows, "Data/nhl_team_stats_free.csv")
    print(f"Saved NHL: {len(rows)} rows → Data/nhl_team_stats_free.csv")
