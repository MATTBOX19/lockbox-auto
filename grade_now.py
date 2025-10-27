#!/usr/bin/env python3
"""
Manual grading trigger for LockBox.
Reuses predictor_min.grading() logic to update history.csv instantly.
"""
import os
from predictor_min import main as predictor_main   # uses your existing model entry

if __name__ == "__main__":
    print("⚡ Manual grading trigger started...")
    predictor_main(force_grade=True)
    print("✅ Manual grading completed — check Output/history.csv")
