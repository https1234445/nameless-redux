"""Offline PING LAB history tests: validation, retention and comparisons."""
import os
import sys
from pathlib import Path
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from ping_history import (
    HISTORY_FORMAT, HISTORY_LIMIT, make_entry, add_entry,
    validate_history, compare_entries, history_text)

a = {"attempts": 4, "successes": 3, "connection_failures": 1,
     "failure_percent": 25.0, "median_ms": 18.0, "jitter_ms": 3.0}
b = dict(a, median_ms=30.0, failure_percent=50.0)
first = make_entry("Cloudflare DNS / TCP 443", a, "2026-01-01T10:00:00+00:00")
second = make_entry("Cloudflare DNS / TCP 443", b, "2026-01-01T11:00:00+00:00")
assert "+12.0 ms" in compare_entries(first, second)
assert "+25.0" in compare_entries(first, second)
assert "LATEST SAME-ENDPOINT" in history_text([first, second])
assert "SAME endpoint" in compare_entries(
    first, make_entry("Google DNS / TCP 443", b))
entries = []
for _ in range(HISTORY_LIMIT + 5):
    entries = add_entry(entries, first)
assert len(entries) == HISTORY_LIMIT
assert validate_history({"format": HISTORY_FORMAT, "entries": entries}) == entries
assert validate_history({"format": "wrong", "entries": entries}) == []
assert validate_history({"format": HISTORY_FORMAT, "entries": ["bad", first]}) == [first]
for bad in ({}, dict(a, attempts=0), dict(a, failure_percent=200)):
    try:
        make_entry("Cloudflare DNS / TCP 443", bad)
    except ValueError:
        pass
    else:
        raise AssertionError("Accepted malformed diagnostic")
print("PING LAB history: retention, validation and trends OK")
