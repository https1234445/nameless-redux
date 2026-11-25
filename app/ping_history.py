"""Bounded, local-only history for PING LAB reference TCP checks.

Never stores IP addresses of players, game packets, or network credentials.
"""
from datetime import datetime, timezone

HISTORY_LIMIT = 60
HISTORY_FORMAT = "nameless-ping-history-v1"


def make_entry(endpoint, result, when=None):
    if not isinstance(endpoint, str) or endpoint not in (
            "Cloudflare DNS / TCP 443", "Google DNS / TCP 443"):
        raise ValueError("Unknown reference endpoint")
    if not isinstance(result, dict):
        raise ValueError("Invalid diagnostic")
    required = ("attempts", "successes", "connection_failures",
                "failure_percent", "median_ms", "jitter_ms")
    if any(k not in result for k in required):
        raise ValueError("Incomplete diagnostic")
    if (not isinstance(result["attempts"], int) or result["attempts"] < 1 or
            not isinstance(result["successes"], int) or
            not 0 <= result["successes"] <= result["attempts"] or
            result["connection_failures"] != result["attempts"] - result["successes"]):
        raise ValueError("Invalid sample counts")
    for key in ("failure_percent", "median_ms", "jitter_ms"):
        val = result[key]
        if val is not None and (not isinstance(val, (int, float)) or
                                isinstance(val, bool) or not 0 <= val <= 100000):
            raise ValueError("Invalid metric")
    if not 0 <= result["failure_percent"] <= 100:
        raise ValueError("Invalid failure rate")
    stamp = when or datetime.now(timezone.utc).isoformat()
    if not isinstance(stamp, str) or len(stamp) > 48:
        raise ValueError("Invalid timestamp")
    return {"utc": stamp, "endpoint": endpoint,
            "result": {key: result[key] for key in required}}


def validate_history(payload):
    if not isinstance(payload, dict) or payload.get("format") != HISTORY_FORMAT:
        return []
    entries = payload.get("entries")
    if not isinstance(entries, list):
        return []
    clean = []
    for entry in entries[-HISTORY_LIMIT:]:
        try:
            if not isinstance(entry, dict):
                continue
            clean.append(make_entry(
                entry["endpoint"], entry["result"], entry["utc"]))
        except (KeyError, ValueError, TypeError):
            continue
    return clean


def add_entry(entries, entry):
    return (entries + [entry])[-HISTORY_LIMIT:]


def compare_entries(older, newer):
    if older["endpoint"] != newer["endpoint"]:
        return "Select two checks of the SAME endpoint for comparison."
    a, b = older["result"], newer["result"]
    if a["median_ms"] is None or b["median_ms"] is None:
        return "No median comparison available: one test had no successful connections."
    change = round(b["median_ms"] - a["median_ms"], 1)
    failure_change = round(b["failure_percent"] - a["failure_percent"], 1)
    return ("Median TCP connect time: %+.1f ms; connection failure rate: %+.1f "
            "percentage points. Neither measures ROB RUN packet loss." %
            (change, failure_change))


def history_text(entries):
    if not entries:
        return "No saved checks yet. Run a connection check to start your local history."
    lines = []
    for index, entry in enumerate(reversed(entries[-HISTORY_LIMIT:]), 1):
        r = entry["result"]
        lines.append("%02d  %s  |  %s\n    Median: %s ms  |  Failed: %s%%  |  Variation: %s ms" %
                     (index, entry["utc"][:19], entry["endpoint"],
                      r["median_ms"], r["failure_percent"], r["jitter_ms"]))
    if len(entries) >= 2:
        last = entries[-1]
        prior = next((e for e in reversed(entries[:-1])
                      if e["endpoint"] == last["endpoint"]), None)
        if prior:
            lines.insert(0, "LATEST SAME-ENDPOINT COMPARISON\n" +
                         compare_entries(prior, last) + "\n")
    return "\n\n".join(lines)
