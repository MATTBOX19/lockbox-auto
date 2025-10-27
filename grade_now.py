#!/usr/bin/env python3
"""Manual grading trigger for LockBox"""
import subprocess

if __name__ == "__main__":
    print("⚡ Manual grading trigger started...")
    try:
        result = subprocess.run(
            ["python", "predictor_min.py"],
            capture_output=True, text=True, timeout=300
        )
        print(result.stdout)
        if result.stderr:
            print(result.stderr)
        print("✅ Manual grading completed — check Output/history.csv")
    except Exception as e:
        print(f"❌ Error: {e}")
