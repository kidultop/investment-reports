#!/usr/bin/env python3
"""
fetch_market_data.py
--------------------
抓取每日投资报告所需的市场数据。
支持：美股指数、欧洲指数、亚洲指数、澳洲指数、中国参考指数、持仓个股、ETF、贵金属/大宗商品、汇率、债券收益率。
"""

import argparse
import glob
import json
import os
import random
import site
import ssl
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime

# 自动挂载用户级及 Homebrew Python site-packages，确保定时任务下能找到 yfinance
for pattern in [
    os.path.expanduser("~/Library/Python/*/lib/python/site-packages"),
    "/opt/homebrew/lib/python*/site-packages",
    "/usr/local/lib/python*/site-packages",
]:
    for p in glob.glob(pattern):
        if p not in sys.path:
            site.addsitedir(p)

_SSL_CTX = ssl._create_unverified_context()

try:
    import yfinance as yf
    import pandas as pd
    HAS_YFINANCE = True
except ImportError:
    HAS_YFINANCE = False


WATCHLIST = {
    "us_indices": {
        "S&P 500":     "^GSPC",
        "NASDAQ":      "^IXIC",
        "Dow Jones":   "^DJI",
        "VIX":         "^VIX",
    },
    "europe_indices": {
        "FTSE 100 (UK)":       "^FTSE",
        "DAX 40 (DE)":         "^GDAXI",
        "CAC 40 (FR)":         "^FCHI",
        "Euro Stoxx 50":       "^STOXX50E",
        "SMI (CH)":            "^SSMI",
    },
    "asia_indices": {
        "Hang Seng (HK)":  "^HSI",
        "Nikkei 225 (JP)": "^N225",
        "KOSPI (KR)":      "^KS11",
        "NIFTY 50 (IN)":   "^NSEI",
        "Taiwan TWII":     "^TWII",
        "STI (SG)":        "^STI",
    },
    "australia_indices": {
        "ASX 200 (AU)":        "^AXJO",
        "All Ordinaries (AU)": "^AORD",
    },
    "china_indices": {
        "上证综合 SSE":    "000001.SS",
        "深证成分 SZSE":   "399001.SZ",
        "沪深300 CSI300":  "000300.SS",
        "科创50 STAR":     "000688.SS",
    },
    "us_stocks": {
        "NVDA":  "NVDA",
        "GOOGL": "GOOGL",
        "AAPL":  "AAPL",
        "MSFT":  "MSFT",
        "AMD":   "AMD",
        "SNDK":  "SNDK",
        "IBM":   "IBM",
        "JNJ":   "JNJ",
        "KO":    "KO",
        "PG":    "PG",
        "VT":    "VT",
        "SPCX":  "SPCX",
        "SKHY":  "SKHY",
    },
    "etf_commodities": {
        "IAU (Gold ETF)":    "IAU",
        "SLV (Silver ETF)":  "SLV",
        "EWJ (Japan ETF)":   "EWJ",
    },
    "forex": {
        "DXY (USD Index)":   "DX-Y.NYB",
        "USD/JPY":           "JPY=X",
        "USD/SGD":           "SGD=X",
        "USD/CNY":           "CNY=X",
        "USD/KRW":           "KRW=X",
        "USD/TWD":           "TWD=X",
    },
    "bonds": {
        "US 10Y Treasury":  "^TNX",
        "US 2Y Treasury":   "^IRX",
    },
    "commodities_spot": {
        "Gold Spot":    "GC=F",
        "Silver Spot":  "SI=F",
        "Brent Crude":  "BZ=F",
        "WTI Crude":    "CL=F",
        "Copper":       "HG=F",
    },
}

SG_FUNDS = [
    {"name": "AB Low Volatility Equity Portfolio A SGD-H",   "short": "AB Low Vol"},
    {"name": "BGF Global Multi-Asset Income Fund A6 SGD-H",  "short": "BGF Multi-Asset"},
    {"name": "Infinity Global Stock Index Fund SGD",          "short": "Infinity Global"},
    {"name": "Infinity US 500 Stock Index Fund SGD",          "short": "Infinity US500"},
    {"name": "LionGlobal Japan Growth Fund (SGD Hedged)",     "short": "LionGlobal Japan"},
    {"name": "LionGlobal Singapore Dividend Equity Fund SGD", "short": "LionGlobal SG Div"},
    {"name": "LionGlobal Singapore Trust Fund SGD",           "short": "LionGlobal SG Trust"},
    {"name": "PIMCO GIS Income Fund E SGD-H Dist",           "short": "PIMCO Income"},
]


def fetch_ticker_urllib(symbol: str, name: str) -> dict:
    """使用标准库 urllib 从 Yahoo Finance v8 API 获取单标的行情（带 query1/query2 轮询与退避防 429）"""
    encoded = urllib.parse.quote(symbol)
    hosts = ["query1.finance.yahoo.com", "query2.finance.yahoo.com"]
    last_err = ""
    for attempt in range(3):
        host = hosts[attempt % 2]
        url = f"https://{host}/v8/finance/chart/{encoded}?interval=1d&range=5d"
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": (
                    f"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    f"AppleWebKit/537.36 (KHTML, like Gecko) Chrome/12{attempt}.0.0.0 Safari/537.36"
                ),
                "Accept": "application/json",
            },
        )
        try:
            time.sleep(0.2 + random.uniform(0.05, 0.15))
            with urllib.request.urlopen(req, timeout=12, context=_SSL_CTX) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            result = payload["chart"]["result"][0]
            meta = result.get("meta", {})
            indicators = result.get("indicators", {}).get("quote", [{}])[0]
            closes = [round(float(c), 4) for c in (indicators.get("close") or []) if c is not None]
            volumes = [int(v) for v in (indicators.get("volume") or []) if v is not None]

            price = meta.get("regularMarketPrice")
            if price is not None:
                price = round(float(price), 4)
            elif closes:
                price = closes[-1]
            else:
                return {"name": name, "symbol": symbol, "error": "No price data"}

            prev_price = None
            if len(closes) >= 2 and abs(closes[-1] - price) < max(0.05 * price, 1.0):
                prev_price = closes[-2]
            if prev_price is None:
                prev_raw = meta.get("previousClose") or meta.get("chartPreviousClose")
                prev_price = round(float(prev_raw), 4) if prev_raw else price

            vol = meta.get("regularMarketVolume")
            volume = int(vol) if vol is not None else (volumes[-1] if volumes else 0)

            change = round(price - prev_price, 4)
            change_pct = round((change / prev_price) * 100, 2) if prev_price != 0 else 0.0
            ts = meta.get("regularMarketTime")
            ts_str = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M") if ts else ""

            return {
                "name": name,
                "symbol": symbol,
                "price": price,
                "prev_close": prev_price,
                "change": change,
                "change_pct": change_pct,
                "volume": volume,
                "direction": "up" if change > 0 else ("down" if change < 0 else "flat"),
                "timestamp": ts_str,
            }
        except Exception as e:
            last_err = str(e)
            time.sleep(0.6 * (attempt + 1))
    return {"name": name, "symbol": symbol, "error": last_err}


def _quote_snapshot_yf(ticker):
    def _clean(v):
        try:
            v = float(v)
            return v if v > 0 else None
        except (TypeError, ValueError):
            return None

    try:
        i = ticker.info or {}
        last = _clean(i.get("regularMarketPrice")) or _clean(i.get("currentPrice"))
        prev = _clean(i.get("previousClose")) or _clean(i.get("regularMarketPreviousClose"))
        if last and prev:
            return (round(last, 4), round(prev, 4), int(i.get("regularMarketVolume") or 0))
    except Exception:
        pass
    try:
        fi = ticker.fast_info
        last = _clean(fi.get("lastPrice"))
        prev = _clean(fi.get("previousClose"))
        if last and prev:
            return (round(last, 4), round(prev, 4), int(fi.get("lastVolume") or 0))
    except Exception:
        pass
    return None


def fetch_ticker_data(symbol: str, name: str) -> dict:
    if not HAS_YFINANCE:
        return fetch_ticker_urllib(symbol, name)
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="5d")
        hist = hist.dropna(subset=["Close"]) if not hist.empty else hist

        latest = hist.iloc[-1] if not hist.empty else None
        prev = hist.iloc[-2] if len(hist) >= 2 else (hist.iloc[-1] if not hist.empty else None)

        h_last = round(float(latest["Close"]), 4) if latest is not None else None
        h_prev = round(float(prev["Close"]), 4) if prev is not None else None
        volume = int(latest.get("Volume", 0) or 0) if latest is not None else 0
        ts = latest.name if latest is not None else None

        q = _quote_snapshot_yf(ticker)
        if q:
            price, prev_price = q[0], q[1]
            volume = volume or q[2]
        elif h_last is not None:
            price, prev_price = h_last, (h_prev if h_prev is not None else h_last)
        else:
            return fetch_ticker_urllib(symbol, name)

        change = round(price - prev_price, 4)
        change_pct = round((change / prev_price) * 100, 2) if prev_price != 0 else 0

        return {
            "name": name,
            "symbol": symbol,
            "price": price,
            "prev_close": prev_price,
            "change": change,
            "change_pct": change_pct,
            "volume": volume,
            "direction": "up" if change > 0 else ("down" if change < 0 else "flat"),
            "timestamp": ts.strftime("%Y-%m-%d %H:%M") if ts is not None and hasattr(ts, 'strftime') else (str(ts) if ts is not None else ""),
        }
    except Exception:
        return fetch_ticker_urllib(symbol, name)


def fetch_category(category_name: str, symbols: dict) -> list:
    return [fetch_ticker_data(symbol, name) for name, symbol in symbols.items()]


def fetch_all_market_data(mode: str = "full") -> dict:
    engine_label = "yfinance" if HAS_YFINANCE else "urllib Yahoo v8 API"
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 开始抓取市场数据（模式：{mode}，引擎：{engine_label}）...")
    result = {
        "report_mode": mode,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "data": {}
    }

    for cat in WATCHLIST:
        print(f"  → 抓取 {cat}...")
        result["data"][cat] = fetch_category(cat, WATCHLIST[cat])

    result["data"]["sg_funds"] = [
        {**fund, "nav": None, "nav_date": None, "note": "净值需从FundSupermart或各基金公司官网获取（T+2更新）"}
        for fund in SG_FUNDS
    ]

    bonds = result["data"].get("bonds", [])
    us10y = next((b for b in bonds if "10Y" in b["name"]), None)
    us2y = next((b for b in bonds if "2Y" in b["name"]), None)
    if us10y and us2y and "price" in us10y and "price" in us2y:
        spread = round(us10y["price"] - us2y["price"], 3)
        result["data"]["yield_spread"] = {
            "10Y_minus_2Y": spread,
            "status": "正常" if spread > 0 else "倒挂（衰退警示）",
            "us10y": us10y["price"],
            "us2y": us2y["price"],
        }

    print(f"[{datetime.now().strftime('%H:%M:%S')}] 数据抓取完成。")
    return result


def main():
    parser = argparse.ArgumentParser(description="每日投资报告数据抓取工具")
    parser.add_argument("--mode", choices=["morning", "evening", "full"], default="full")
    parser.add_argument("--output", default="market_data.json")
    args = parser.parse_args()

    data = fetch_all_market_data(args.mode)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 数据已保存至：{args.output}")
    return data


if __name__ == "__main__":
    main()
