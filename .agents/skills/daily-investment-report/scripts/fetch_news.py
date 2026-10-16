#!/usr/bin/env python3
"""
fetch_news.py  —  新闻评分、分类、去重工具
---------------------------------------------
职责：
  接收 AI 通过 search_web 抓取的原始新闻条目，
  对其进行权威评分、时效评分、相关性评分、去重、分类，
  输出符合报告格式的 JSON。

使用方式（AI 调用）：
  python3 fetch_news.py --input /tmp/raw_news_YYYYMMDD_morning.json --output /tmp/news_data_YYYYMMDD_morning.json
"""

import json
import sys
import os
import re
import argparse
from datetime import datetime, timedelta, timezone
from typing import List, Dict


# ── 权威媒体评分表 ──────────────────────────────────────────────────────────────
AUTHORITY_SCORES = {
    # Tier 1 — 10分（顶级金融/新闻权威）
    "reuters.com":              10,
    "bloomberg.com":            10,
    "ft.com":                   10,
    # Tier 2 — 9分
    "wsj.com":                   9,
    "economist.com":             9,
    # Tier 3 — 8分
    "bbc.com":                   8,
    "bbc.co.uk":                 8,
    "afp.com":                   8,
    "apnews.com":                8,
    # Tier 4 — 7分
    "nytimes.com":               7,
    "asia.nikkei.com":           7,
    "nikkei.com":                7,
    "dw.com":                    7,
    "washingtonpost.com":        7,
    "guardian.com":              7,
    # Tier 5 — 6分（主流财经媒体）
    "channelnewsasia.com":       6,
    "straitstimes.com":          6,
    "scmp.com":                  6,
    "cnbc.com":                  6,
    "marketwatch.com":           6,
    "cnn.com":                   6,
    "cbsnews.com":               6,
    "nbcnews.com":               6,
    "abcnews.go.com":            6,
    "politico.com":              6,
    "axios.com":                 6,
    "thehill.com":               6,
    "usnews.com":                6,
    "businessinsider.com":       6,
    "fortune.com":               6,
    "barrons.com":               7,
    "morningstar.com":           6,
    "weforum.org":               6,
    "theglobeandmail.com":       7,
    "imf.org":                   7,
    "worldbank.org":             7,
    "federalreserve.gov":        8,
    "ecb.europa.eu":             8,
    "boj.or.jp":                 8,
    "mas.gov.sg":                8,
    "247wallst.com":             5,
    "investing.com":             5,
    "seekingalpha.com":          5,
    "chase.com":                 5,
    "finance.yahoo.com":         6,
    "tradingeconomics.com":       6,
    "toledoblade.com":           6,
    "sec.gov":                   10,
    "reut.rs":                   10,
    "kitco.com":                  6,
    "oilprice.com":               6,
    "clevelandfed.org":           8,
}

DEFAULT_AUTHORITY = 5

ALLOWED_DOMAINS = [
    "reuters.com", "bloomberg.com", "ft.com",
    "wsj.com", "economist.com",
    "bbc.com", "bbc.co.uk", "afp.com", "apnews.com",
    "nytimes.com", "asia.nikkei.com", "nikkei.com", "barrons.com",
    "channelnewsasia.com", "straitstimes.com", "marketwatch.com",
    "finance.yahoo.com", "tradingeconomics.com", "toledoblade.com",
    "theglobeandmail.com", "cnbc.com", "fortune.com",
    "federalreserve.gov", "ecb.europa.eu", "boj.or.jp", "mas.gov.sg",
    "clevelandfed.org",
    "sec.gov", "reut.rs", "kitco.com",
    "oilprice.com",
]

BLOCKED_DOMAINS = [
    "eastmoney.com", "qq.com", "sina.com.cn", "sina.com", "10jqka.com.cn",
    "hexun.com", "cnstock.com", "stcn.com", "cls.cn", "wallstreetcn.com",
    "caixin.com", "yicai.com", "21jingji.com", "jrj.com.cn", "stockstar.com",
    "finance.ifeng.com", "ifeng.com", "sohu.com", "163.com", "qq.com",
    "news.cn", "xinhuanet.com", "people.com.cn", "globaltimes.cn",
    "chinadaily.com.cn", "english.news.cn",
]


def is_blocked_source(source: str) -> bool:
    if not source:
        return True
    domain = source.lower().replace("www.", "").split("/")[0].strip()
    if domain.endswith(".cn") or ".cn." in domain:
        return True
    return any(b in domain for b in BLOCKED_DOMAINS)


def is_allowed_source(source: str) -> bool:
    if not source or is_blocked_source(source):
        return False
    domain = source.lower().replace("www.", "").split("/")[0].strip()
    if domain in ALLOWED_DOMAINS:
        return True
    for key in ALLOWED_DOMAINS:
        if key in domain or domain in key:
            return True
    return False


RELEVANCE_KEYWORDS = [
    "s&p", "nasdaq", "dow", "stock market", "equities",
    "federal reserve", "fed", "fomc", "ecb", "boj", "interest rate", "rate cut", "rate hike",
    "iran", "ukraine", "russia", "china trade", "tariff", "sanctions",
    "nvidia", "nvda", "google", "alphabet", "apple", "microsoft", "amd", "sandisk", "ibm",
    "micron", "spacex",
    "coca-cola", "procter", "p&g",
    "oil", "crude", "gold", "silver", "copper", "opec",
    "nikkei", "hang seng", "kospi", "singapore", "sti", "japan", "korea",
    "inflation", "cpi", "gdp", "unemployment", "nonfarm", "treasury", "yield",
]

CATEGORY_RULES = {
    "Breaking":     ["breaking", "emergency", "urgent", "alert", "just in"],
    "Central Bank": ["federal reserve", "fed", "fomc", "ecb", "boj", "bank of japan",
                     "central bank", "interest rate", "rate cut", "rate hike",
                     "monetary policy", "quantitative"],
    "Geopolitics":  ["iran", "ukraine", "russia", "china", "taiwan", "north korea",
                     "sanction", "trade war", "tariff", "conflict", "war", "military",
                     "diplomatic", "strait", "hormuz"],
    "Market":       ["stock market", "equity", "s&p", "nasdaq", "dow jones", "trading",
                     "bull", "bear", "rally", "selloff", "correction"],
    "Commodities":  ["oil", "crude", "brent", "wti", "gold", "silver", "copper",
                     "natural gas", "opec", "commodity"],
    "Earnings":     ["earnings", "profit", "revenue", "q1", "q2", "q3", "q4",
                     "quarterly", "guidance", "eps", "beats", "misses"],
    "FX":           ["currency", "forex", "exchange rate", "dollar", "euro", "yen",
                     "yuan", "renminbi", "sgd", "gbp", "dxy"],
    "General":      [],
}


def get_authority_score(source: str) -> float:
    if not source:
        return DEFAULT_AUTHORITY
    domain = source.lower().replace("www.", "").split("/")[0].strip()
    if domain in AUTHORITY_SCORES:
        return float(AUTHORITY_SCORES[domain])
    for key, score in AUTHORITY_SCORES.items():
        if key in domain or domain in key:
            return float(score)
    return float(DEFAULT_AUTHORITY)


def get_time_score(published_time: str) -> float:
    if not published_time:
        return 5.0
    try:
        ts = published_time.replace("Z", "+00:00")
        pub = datetime.fromisoformat(ts)
        now = datetime.now(pub.tzinfo or timezone.utc)
        hours = (now - pub).total_seconds() / 3600
        if hours < 2:   return 10.0
        if hours < 6:   return 8.0
        if hours < 12:  return 6.0
        if hours < 24:  return 4.0
        return 2.0
    except Exception:
        return 5.0


def get_relevance_score(title: str, snippet: str) -> float:
    text = (title + " " + (snippet or "")).lower()
    matches = sum(1 for kw in RELEVANCE_KEYWORDS if kw in text)
    if matches >= 4:  return 10.0
    if matches >= 2:  return 8.0
    if matches == 1:  return 5.0
    return 2.0


def total_score(authority: float, time_s: float, relevance: float) -> float:
    return round(authority * 0.5 + time_s * 0.3 + relevance * 0.2, 2)


def categorize(title: str, snippet: str) -> str:
    text = (title + " " + (snippet or "")).lower()
    for cat, keywords in CATEGORY_RULES.items():
        if cat == "General":
            continue
        for kw in keywords:
            try:
                if re.search(r"\b" + re.escape(kw) + r"\b", text):
                    return cat
            except re.error:
                if kw in text:
                    return cat
    return "General"


def deduplicate(items: List[Dict]) -> List[Dict]:
    seen: List[str] = []
    result = []
    items = sorted(items, key=lambda x: x.get("authority_score", 0), reverse=True)
    for item in items:
        title = item.get("title", "").lower()
        words = set(title.split())
        is_dup = False
        for s in seen:
            s_words = set(s.split())
            if len(words) == 0 or len(s_words) == 0:
                continue
            overlap = len(words & s_words) / max(len(words), len(s_words), 1)
            if overlap >= 0.55:
                is_dup = True
                break
        if not is_dup:
            result.append(item)
            seen.append(title)
    return result


def process_news(raw_items: List[Dict]) -> Dict:
    scored = []
    blocked_count = 0
    for item in raw_items:
        title   = item.get("title", "")
        snippet = item.get("snippet", "") or item.get("summary", "") or ""
        snippet_cn = item.get("snippet_cn", "") or item.get("summary_cn", "") or ""
        source  = item.get("source", "")
        pub_t   = item.get("published_time", "")

        if is_blocked_source(source):
            print(f"  ⛔ 已拦截国内来源：{source} — {title[:40]}")
            blocked_count += 1
            continue

        if not is_allowed_source(source):
            print(f"  ⛔ 已拦截非白名单来源：{source} — {title[:40]}")
            blocked_count += 1
            continue

        auth  = get_authority_score(source)
        time_ = get_time_score(pub_t)
        rel   = get_relevance_score(title, snippet)
        score = total_score(auth, time_, rel)

        if score < 5.5:
            continue

        scored.append({
            **item,
            "snippet":    snippet,
            "snippet_cn": snippet_cn,
            "summary":    snippet,
            "summary_cn": snippet_cn,
            "authority_score": auth,
            "time_score":      time_,
            "relevance_score": rel,
            "total_score":     score,
            "category":        categorize(title, snippet),
        })

    deduped = deduplicate(scored)
    sorted_news = sorted(deduped, key=lambda x: x["total_score"], reverse=True)

    by_category: Dict[str, List] = {}
    for item in sorted_news:
        cat = item["category"]
        by_category.setdefault(cat, []).append(item)

    return {
        "timestamp":    datetime.now().isoformat(),
        "total_count":  len(sorted_news),
        "by_category":  by_category,
        "all_news":     sorted_news,
    }, blocked_count


def main():
    parser = argparse.ArgumentParser(description="新闻评分分类工具")
    parser.add_argument("--input",  required=True, help="原始新闻 JSON 文件路径")
    parser.add_argument("--output", default="/tmp/news_data.json", help="输出 JSON 路径")
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"❌ 输入文件不存在：{args.input}")
        sys.exit(1)

    with open(args.input, "r", encoding="utf-8") as f:
        raw_items = json.load(f)

    if not isinstance(raw_items, list):
        print("❌ 输入文件格式错误：应为 JSON 数组")
        sys.exit(1)

    result, blocked_count = process_news(raw_items)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"✓ 处理完成：共 {result['total_count']} 条新闻通过筛选")
    if blocked_count:
        print(f"⛔ 已拦截国内来源条目：{blocked_count} 条（用户要求仅用国外权威源）")
    print(f"✓ 分类分布：{', '.join(f'{k}({len(v)})' for k, v in result['by_category'].items())}")
    print(f"✓ 已写入：{args.output}")


if __name__ == "__main__":
    main()
