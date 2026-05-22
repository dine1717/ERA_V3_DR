"""Print a friendly summary of Tavily / DuckDuckGo usage for the current month.

Reads usage.json (written by mcp_server.py). Run any time:

    uv run usage_status.py            # summary + last 10 calls
    uv run usage_status.py --all      # summary + full call log
    uv run usage_status.py --json     # raw JSON
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

USAGE_PATH = Path(__file__).parent / "usage.json"


def _load() -> dict:
    if not USAGE_PATH.exists():
        return {
            "month": "(no calls yet)",
            "tavily": {"count": 0, "errors": 0, "free_quota": 1000, "soft_cap": 950},
            "duckduckgo": {"count": 0, "errors": 0},
            "calls": [],
        }
    return json.loads(USAGE_PATH.read_text(encoding="utf-8"))


def _bar(used: int, total: int, width: int = 30) -> str:
    if total <= 0:
        return "[" + " " * width + "]"
    filled = min(width, int(round(width * used / total)))
    return "[" + "█" * filled + "·" * (width - filled) + "]"


def _summary(data: dict) -> None:
    tav = data.get("tavily", {})
    ddg = data.get("duckduckgo", {})
    used = tav.get("count", 0)
    quota = tav.get("free_quota", 1000)
    cap = tav.get("soft_cap", 950)
    remaining = max(0, quota - used)
    pct = (used / quota * 100) if quota else 0

    print("=" * 62)
    print(f"Web-search usage for {data.get('month', '?')}")
    print("=" * 62)
    print(f"Tavily       {used:4d} / {quota} used  ({remaining} remaining)")
    print(f"             {_bar(used, quota)}  {pct:5.1f}%")
    if cap < quota:
        print(f"             soft cap: {cap}  (router stops calling Tavily at this number)")
    if tav.get("errors", 0):
        print(f"             errors: {tav['errors']}")
    print()
    print(f"DuckDuckGo   {ddg.get('count', 0):4d}  (fallback; no quota)")
    if ddg.get("errors", 0):
        print(f"             errors: {ddg['errors']}")
    print()


def _calls(data: dict, limit: int | None) -> None:
    calls = data.get("calls", [])
    if not calls:
        print("(no calls logged yet)")
        return
    rows = calls if limit is None else calls[-limit:]
    print(f"Last {len(rows)} call(s):")
    print("-" * 88)
    print(f"{'timestamp':<20} {'provider':<11} {'status':<14} {'#':<4} query")
    print("-" * 88)
    for c in rows:
        ts = c.get("ts", "")[:19]
        prov = c.get("provider", "")[:10]
        st = c.get("status", "")[:13]
        n = c.get("results", 0)
        q = (c.get("query") or "")[:48]
        print(f"{ts:<20} {prov:<11} {st:<14} {n:<4} {q}")


def main() -> None:
    data = _load()
    if "--json" in sys.argv:
        print(json.dumps(data, indent=2))
        return
    _summary(data)
    if "--all" in sys.argv:
        _calls(data, None)
    else:
        _calls(data, 10)


if __name__ == "__main__":
    main()
