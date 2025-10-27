# test_af_adapter.py
from af_adapter import compute_team_stats, match_features

# minimal fake fixture (home team id 10, away team id 20)
sample_fixture = {
    "fixture": {"date": "2025-10-01T19:00:00+00:00", "status": {"short":"FT"}},
    "teams": {"home": {"id": 10, "name":"Home"}, "away": {"id": 20, "name":"Away"}},
    "score": {"home": 28, "away": 14}
}
print("Team10 stats:", compute_team_stats([sample_fixture], 10))
print("Team20 stats:", compute_team_stats([sample_fixture], 20))
t1 = compute_team_stats([sample_fixture], 10)
t2 = compute_team_stats([sample_fixture], 20)
print("Features:", match_features(t1,t2))
