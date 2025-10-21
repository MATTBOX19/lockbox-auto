# lockbox_web.py
#
# Flask app to show LockBox predictions with:
# - sport dropdown (All / NFL / NCAA / NBA / NHL / MLB + any found in CSV)
# - Top 5 toggle (by Edge)
# - Lock emoji (🔒), Upset (🚨), Confidence(%) and Edge(%)
# - Moneyline (ML), ATS and O/U if present in CSV (otherwise shows N/A)
#
# Usage: replace the file in your repo root and deploy. It looks for Output/Predictions_*.csv

from flask import Flask, request, render_template_string
import pandas as pd
import glob, os, datetime, re

app = Flask(__name__)

TEMPLATE = """ (same template as before - you can keep your existing template) """
# For brevity in this message the HTML/CSS template is the same as the one you already used.
# If you want the full template inline, copy the template string you prefer above exactly here.
# The Python logic below produces the `rows` and template context.

def find_latest_prediction_csv():
    patterns = ["Output/Predictions_*.csv", "Output/*.csv", "Predictions_*.csv"]
    candidates = []
    for p in patterns:
        candidates.extend(glob.glob(p))
    if not candidates:
        return None
    candidates = sorted(candidates, key=lambda x: os.path.getmtime(x), reverse=True)
    return candidates[0]

def find_col(df, candidates):
    # case-insensitive exact match, then contains match
    cols = {c.lower(): c for c in df.columns}
    for cand in candidates:
        if cand is None: 
            continue
        cl = cand.lower()
        if cl in cols:
            return cols[cl]
    for cand in candidates:
        if cand is None:
            continue
        cl = cand.lower()
        for c in df.columns:
            if cl in c.lower():
                return c
    return None

def parse_percentish(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    s = str(v).strip()
    if s == "":
        return None
    # remove % and commas
    s2 = s.replace("%","").replace(",","").strip()
    # sometimes values like "3.0%" or "101.4" or "3"
    try:
        return float(s2)
    except Exception:
        return None

def parse_moneyline_numeric(s):
    if s is None:
        return None
    s = str(s).strip()
    # look for + or - followed by digits
    m = re.search(r'([+-]?\d+)', s)
    if m:
        try:
            return int(m.group(1))
        except:
            return None
    return None

def normalize_sport_name(s):
    if not s:
        return "Unknown"
    s = str(s).strip().lower()
    if "nfl" in s or "americanfootball" in s:
        return "NFL"
    if "college" in s or "ncaa" in s or "ncaaf" in s or "collegefootball" in s:
        return "NCAA"
    if "nba" in s or "basketball" in s:
        return "NBA"
    if "mlb" in s or "baseball" in s:
        return "MLB"
    if "nhl" in s or "icehockey" in s or "hockey" in s:
        return "NHL"
    # fallback: uppercase short token
    return s.upper()

@app.route("/")
def index():
    csv_path = find_latest_prediction_csv()
    if not csv_path:
        return render_template_string(TEMPLATE, rows=[], sport_options=[], selected_sport="All", top5=False, updated_at="No data")

    try:
        df = pd.read_csv(csv_path)
    except Exception as e:
        return f"Error reading CSV: {e}", 500

    # candidate column names (many variants)
    sport_col = find_col(df, ["sport","Sport","category","league"])
    team1_col = find_col(df, ["team1","home","home_team","team_a","team1_name","home_team_name"])
    team2_col = find_col(df, ["team2","away","away_team","team_b","team2_name","away_team_name"])
    gametime_col = find_col(df, ["gametime","game_time","datetime","date","start","kickoff","start_time"])
    pick_col = find_col(df, ["pick","Pick","moneylinepick","ml_pick","predicted_winner","pick_team","selected","our_pick"])
    conf_col = find_col(df, ["confidence","Confidence","confidence_percent","conf","confidence(%)"])
    edge_col = find_col(df, ["edge","Edge","model_edge"])
    lock_col = find_col(df, ["lock","is_lock","lockemoji","lock_emoji"])
    upset_col = find_col(df, ["upset","is_upset","upsetemoji","upset_emoji","underdog"])
    ml_col = find_col(df, ["ml","moneyline","moneyline_home","moneyline_away","home_ml","away_ml"])
    ats_col = find_col(df, ["ats","spread","line","against_the_spread"])
    ou_col = find_col(df, ["ou","overunder","total","o/u","over_under"])
    reason_col = find_col(df, ["reason","Reason","explanation","Model vs Market","model_reason"])

    rows = []
    for _, r in df.iterrows():
        t1 = r[team1_col] if team1_col and team1_col in df.columns else r.get("Team1") or ""
        t2 = r[team2_col] if team2_col and team2_col in df.columns else r.get("Team2") or ""
        title = f"{t1} vs {t2}".strip()

        gametime = ""
        if gametime_col and gametime_col in df.columns:
            val = r[gametime_col]
            gametime = "" if pd.isna(val) else str(val)

        # pick
        pick = "N/A"
        if pick_col and pick_col in df.columns:
            val = r[pick_col]
            if pd.notna(val) and str(val).strip() != "":
                pick = str(val).strip()

        # confidence
        conf_val = None
        if conf_col and conf_col in df.columns:
            conf_val = parse_percentish(r[conf_col])
        if conf_val is None:
            conf_display = "0.0%"
        else:
            conf_display = f"{round(conf_val,1)}%"

        # edge
        edge_val = None
        if edge_col and edge_col in df.columns:
            edge_val = parse_percentish(r[edge_col])
        edge_display = "N/A" if edge_val is None else f"{round(edge_val,1)}%"

        # lock (explicit column or fallback threshold)
        lock = False
        if lock_col and lock_col in df.columns:
            v = r[lock_col]
            lock = bool(v) and str(v).strip().lower() not in ("", "0", "false", "none", "nan")
        else:
            if edge_val is not None and edge_val >= 5.0:
                lock = True

        # upset
        upset = False
        if upset_col and upset_col in df.columns:
            v = r[upset_col]
            upset = bool(v) and str(v).strip().lower() not in ("", "0", "false", "none", "nan")
        else:
            # try to detect upsets from moneyline positive numeric for pick
            ml_try = None
            if ml_col and ml_col in df.columns:
                ml_try = r[ml_col]
                ml_num = parse_moneyline_numeric(ml_try)
                if ml_num is not None and ml_num > 0:
                    upset = True

        # ml / ats / ou formatting
        ml_display = "N/A"
        if ml_col and ml_col in df.columns:
            v = r[ml_col]
            ml_display = str(v) if pd.notna(v) else "N/A"
        else:
            # try home/away two columns
            h = find_col(df, ["home_ml","home moneyline","home_ml_value"])
            a = find_col(df, ["away_ml","away moneyline","away_ml_value"])
            if h and a:
                hv = r[h] if pd.notna(r[h]) else ""
                av = r[a] if pd.notna(r[a]) else ""
                ml_display = f"{hv} / {av}" if hv or av else "N/A"

        ats_display = "N/A"
        if ats_col and ats_col in df.columns:
            v = r[ats_col]
            ats_display = str(v) if pd.notna(v) else "N/A"

        ou_display = "N/A"
        if ou_col and ou_col in df.columns:
            v = r[ou_col]
            ou_display = str(v) if pd.notna(v) else "N/A"

        reason = ""
        if reason_col and reason_col in df.columns:
            reason = str(r[reason_col]) if pd.notna(r[reason_col]) else ""
        if not reason:
            reason = "Model vs Market probability differential"

        sport_raw = r[sport_col] if sport_col and sport_col in df.columns else r.get("league") or ""
        sport = normalize_sport_name(sport_raw)

        rows.append({
            "sport": sport,
            "title": title,
            "gametime": gametime,
            "pick": pick,
            "confidence": conf_display,
            "edge": edge_display,
            "edge_val": edge_val if edge_val is not None else 0.0,
            "lock": lock,
            "upset": upset,
            "ml": ml_display,
            "ats": ats_display,
            "ou": ou_display,
            "reason": reason
        })

    # sport options (ordered preference + rest)
    seen = sorted({r["sport"] for r in rows if r["sport"]})
    preferred = ["NFL","NCAA","NBA","NHL","MLB"]
    sport_options = [p for p in preferred if p in seen] + [s for s in seen if s not in preferred]

    # apply filters
    selected_sport = (request.args.get("sport") or "All")
    top5_flag = request.args.get("top5","0") in ("1","true","True")

    filtered = [r for r in rows if selected_sport in ("All","") or r["sport"].strip().lower() == selected_sport.strip().lower()]

    # sort by numeric edge_val desc
    filtered_sorted = sorted(filtered, key=lambda x: x.get("edge_val",0.0), reverse=True)

    if top5_flag:
        filtered_sorted = filtered_sorted[:5]

    # updated at
    try:
        mt = os.path.getmtime(csv_path)
        updated_at = datetime.datetime.utcfromtimestamp(mt).strftime("%Y-%m-%d %H:%M UTC")
    except:
        updated_at = datetime.datetime.utcnow().isoformat()

    return render_template_string(TEMPLATE,
                                 rows=filtered_sorted,
                                 sport_options=sport_options,
                                 selected_sport=selected_sport,
                                 top5=top5_flag,
                                 updated_at=updated_at)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)), debug=False)
