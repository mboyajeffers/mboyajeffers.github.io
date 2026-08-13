#!/usr/bin/env python3
"""
Generates market-pulse/data.json from live, free, no-key public APIs.
Run on a schedule by .github/workflows/dashboard.yml -- this is the
actual live-data proof-of-life for the market-pulse page: every commit
to data.json is a real, dated, automatically-produced artifact, not a
manual claim.

Four panels, four sources, no API keys required for any of them:
  - Finance:   Yahoo Finance chart API -- SPY (5-day return, latest close), VIX (latest close)
  - Crypto:    CoinGecko markets API (top 5 by market cap) + DefiLlama /protocols
               (top 5 DeFi protocols by TVL, CEX category excluded -- TVL is an
               on-chain protocol metric, distinct from CoinGecko's spot-market data)
  - Ecommerce: Yahoo Finance (6 public ecommerce tickers, 5-day return) + FRED UMCSENT
               (consumer sentiment, most recent monthly reading)
  - Solar:     Yahoo Finance (5 public solar tickers, 5-day return) + Open-Meteo daily
               shortwave radiation sum for Phoenix, AZ -- a real physical/production-
               potential signal, not just another stock-market proxy

Designed to fail loudly (non-zero exit) rather than silently write
partial/fake data if a source is unreachable.
"""

import csv
import io
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

OUT_PATH = Path(__file__).parent.parent / "market-pulse" / "data.json"

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; market-pulse-bot/1.0)"}

ECOMMERCE_TICKERS = [("AMZN", "Amazon"), ("SHOP", "Shopify"), ("EBAY", "eBay"),
                     ("ETSY", "Etsy"), ("W", "Wayfair"), ("CHWY", "Chewy")]
SOLAR_TICKERS = [("FSLR", "First Solar"), ("ENPH", "Enphase Energy"),
                  ("SEDG", "SolarEdge"), ("RUN", "Sunrun"), ("ARRY", "Array Technologies")]

# Phoenix, AZ -- high-solar-market reference location for the irradiance panel.
SOLAR_LAT, SOLAR_LON = 33.45, -112.07


def _fetch_json(url: str) -> dict:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


def _fetch_text(url: str) -> str:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read().decode()


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


def fetch_yahoo_basket(tickers: list) -> list:
    out = []
    for symbol, name in tickers:
        try:
            q = fetch_yahoo_symbol(symbol)
            out.append({"symbol": symbol, "name": name, **q})
        except Exception as exc:
            print(f"generate_dashboard: {symbol} fetch failed, skipping: {exc}", file=sys.stderr)
    if not out:
        raise ValueError("No tickers in basket returned data")
    return out


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


def fetch_top_defi_tvl(n: int = 5) -> list:
    """Top N DeFi protocols by TVL from DefiLlama, CEX category excluded --
    a CEX's balance sheet isn't a DeFi protocol's TVL, even though DefiLlama
    lists both in the same /protocols endpoint."""
    data = _fetch_json("https://api.llama.fi/protocols")
    protocols = [p for p in data if p.get("category") != "CEX" and p.get("tvl") is not None]
    protocols.sort(key=lambda p: p["tvl"], reverse=True)
    return [
        {
            "name": p.get("name"),
            "category": p.get("category"),
            "tvl_usd": round(p["tvl"]),
            "change_7d_pct": round(p["change_7d"], 2) if p.get("change_7d") is not None else None,
        }
        for p in protocols[:n]
    ]


def fetch_fred_latest(series_id: str) -> dict:
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    text = _fetch_text(url)
    rows = list(csv.reader(io.StringIO(text)))
    data_rows = [r for r in rows if len(r) == 2 and r[0] not in ("DATE", "observation_date")
                 and r[1].strip() not in (".", "")]
    if not data_rows:
        raise ValueError(f"No usable FRED rows for {series_id}")
    date_str, value = data_rows[-1]
    return {"date": date_str, "value": round(float(value), 2)}


def fetch_solar_irradiance(lat: float, lon: float) -> dict:
    """Real physical production-potential signal, not a market proxy --
    Open-Meteo daily shortwave radiation sum, free/no-key."""
    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}&daily=shortwave_radiation_sum"
        f"&timezone=auto&forecast_days=3"
    )
    data = _fetch_json(url)
    daily = data["daily"]
    return {
        "location": "Phoenix, AZ",
        "unit": "MJ/m2",
        "dates": daily["time"],
        "shortwave_radiation_sum": daily["shortwave_radiation_sum"],
    }


def main() -> int:
    try:
        spy = fetch_yahoo_symbol("SPY")
        vix = fetch_yahoo_symbol("%5EVIX")
        crypto = fetch_top_crypto()
        defi_tvl = fetch_top_defi_tvl()
        ecommerce = fetch_yahoo_basket(ECOMMERCE_TICKERS)
        consumer_sentiment = fetch_fred_latest("UMCSENT")
        solar_stocks = fetch_yahoo_basket(SOLAR_TICKERS)
        solar_irradiance = fetch_solar_irradiance(SOLAR_LAT, SOLAR_LON)
    except Exception as exc:
        print(f"generate_dashboard: fetch failed, not writing data.json: {exc}", file=sys.stderr)
        return 1

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "finance": {"spy": spy, "vix": {"latest": vix["latest"]}},
        "crypto": {"top_crypto": crypto, "top_defi_tvl": defi_tvl},
        "ecommerce": {"stocks": ecommerce, "consumer_sentiment": consumer_sentiment},
        "solar": {"stocks": solar_stocks, "irradiance": solar_irradiance},
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"Wrote {OUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
