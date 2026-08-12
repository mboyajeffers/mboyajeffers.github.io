#!/usr/bin/env python3
"""
Generates market-pulse/data.json from live, free, no-key public APIs.
Run on a schedule by .github/workflows/dashboard.yml -- this is the
actual live-data proof-of-life for the market-pulse page: every commit
to data.json is a real, dated, automatically-produced artifact, not a
manual claim.

Sources:
  - Yahoo Finance chart API: SPY (5-day return, latest close), VIX (latest close)
  - CoinGecko markets API: top 5 coins by market cap, 24h change

No API key required for either. Designed to fail loudly (non-zero exit)
rather than silently write partial/fake data if a source is unreachable.
"""

import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

OUT_PATH = Path(__file__).parent.parent / "market-pulse" / "data.json"

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; market-pulse-bot/1.0)"}


def _fetch_json(url: str) -> dict:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


def fetch_yahoo_symbol(symbol: str) -> dict:
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        f"?range=6d&interval=1d"
    )
    data = _fetch_json(url)
    result = data["chart"]["result"][0]
    closes = [c for c in result["indicators"]["quote"][0]["close"] if c is not None]
    if len(closes) < 2:
        raise ValueError(f"Not enough close data for {symbol}")
    latest = closes[-1]
    five_day_return_pct = (closes[-1] / closes[0] - 1) * 100
    return {"latest": round(latest, 2), "five_day_return_pct": round(five_day_return_pct, 2)}


def fetch_top_crypto(n: int = 5) -> list:
    url = (
        "https://api.coingecko.com/api/v3/coins/markets"
        f"?vs_currency=usd&order=market_cap_desc&per_page={n}&page=1"
        "&price_change_percentage=24h"
    )
    data = _fetch_json(url)
    return [
        {
            "symbol": c["symbol"].upper(),
            "price_usd": c["current_price"],
            "change_24h_pct": round(c.get("price_change_percentage_24h") or 0, 2),
        }
        for c in data
    ]


def main() -> int:
    try:
        spy = fetch_yahoo_symbol("SPY")
        vix = fetch_yahoo_symbol("%5EVIX")
        crypto = fetch_top_crypto()
    except Exception as exc:
        print(f"generate_dashboard: fetch failed, not writing data.json: {exc}", file=sys.stderr)
        return 1

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "spy": spy,
        "vix": {"latest": vix["latest"]},
        "top_crypto": crypto,
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"Wrote {OUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
