#!/usr/bin/env python3
"""
generate_report.py
------------------
读取 market_data.json，生成 HTML 格式的每日投资报告。
"""

import json
import argparse
import os
import re
import sys
from datetime import datetime


def color_class(direction: str) -> str:
    if direction == "up":
        return "up"
    elif direction == "down":
        return "down"
    return "neutral"


def arrow(direction: str) -> str:
    return "▲" if direction == "up" else ("▼" if direction == "down" else "─")


def format_change(change_pct: float) -> str:
    sign = "+" if change_pct >= 0 else ""
    return f"{sign}{change_pct:.2f}%"


def bilingual(key: str, zh: str, en: str) -> str:
    return f'<span class="zh">{zh}</span> <span class="en">({en})</span>'


COST_BASIS = {
    "NVDA":  184.463,
    "GOOGL": 244.70,
    "GOOG":  244.70,
    "AAPL":  257.397,
    "AMD":   180.19,
    "SNDK":  205.33,
    "MSFT":  515.00,
    "IBM":   305.022,
    "JNJ":   229.313,
    "KO":    66.19,
    "PG":    150.81,
    "IAU":   88.95,
    "SLV":   44.268,
    "EWJ":   83.418,
    "SPCX":  151.65,
    "VT":    154.322,
    "SKHY":  152.00,
}


def build_ticker_row(item: dict, show_volume: bool = False, show_cost: bool = False) -> str:
    if "error" in item:
        return f"""
        <tr class="ticker-row error-row">
            <td><span class="symbol">{item['symbol']}</span></td>
            <td colspan="4" class="neutral">数据获取失败: {item['error']}</td>
        </tr>"""

    cls = color_class(item.get("direction", "neutral"))
    arw = arrow(item.get("direction", "neutral"))
    vol = f"<td class='volume'>{item.get('volume', 0):,}</td>" if show_volume else ""

    cost_col = ""
    if show_cost:
        sym = item.get("symbol", "")
        cost = COST_BASIS.get(sym)
        cur_price = item.get("price")
        if cost and cur_price:
            pl_pct = (cur_price - cost) / cost * 100
            pl_cls = "up" if pl_pct >= 0 else "down"
            pl_sign = "+" if pl_pct >= 0 else ""
            cost_col = (
                f"<td class='cost-col'>"
                f"<span class='cost-price'>{cost:,.3f}</span>"
                f"&nbsp;<span class='{pl_cls} cost-pl'>({pl_sign}{pl_pct:.1f}%)</span>"
                f"</td>"
            )
        else:
            cost_col = "<td class='cost-col neutral'>─</td>"

    return f"""
        <tr class="ticker-row">
            <td><span class="symbol">{item['symbol']}</span> <span class="name-label">{item['name']}</span></td>
            <td class="{cls} price">{item.get('price', 'N/A'):,.2f}</td>
            {cost_col}
            <td class="{cls}">{arw} {format_change(item.get('change_pct', 0))}</td>
            <td class="{cls} change-abs">{item.get('change', 0):+,.2f}</td>
            {vol}
        </tr>"""


def generate_html_report(data: dict, mode: str, news_data: dict = None, insights: dict = None) -> str:
    now = datetime.now()
    report_type = "早报 Morning Brief" if mode == "morning" else "晚报 Evening Brief"
    report_subtitle = (
        "隔夜美股收盘 | 亚市开盘预判" if mode == "morning"
        else "亚市收盘总结 | 美股盘前动态"
    )
    generated_at = data.get("generated_at", now.strftime("%Y-%m-%d %H:%M:%S"))
    date_str = now.strftime("%Y年%m月%d日")
    weekday_map = ["周一","周二","周三","周四","周五","周六","周日"]
    weekday = weekday_map[now.weekday()]

    us_indices = data["data"].get("us_indices", [])
    us_index_rows = "".join(build_ticker_row(t) for t in us_indices)

    vix_item = next((t for t in us_indices if t.get("symbol") == "^VIX"), None)
    vix_html = ""
    if vix_item and "price" in vix_item:
        vix_level = vix_item["price"]
        vix_status = "低波动" if vix_level < 15 else ("正常" if vix_level < 25 else ("较高" if vix_level < 35 else "极度恐慌"))
        vix_cls = "up" if vix_level >= 25 else "neutral"
        vix_html = f'<div class="vix-badge {vix_cls}">VIX: {vix_level:.1f} <span class="vix-label">{vix_status}</span></div>'

    europe_indices = data["data"].get("europe_indices", [])
    europe_rows = "".join(build_ticker_row(t) for t in europe_indices)

    asia_indices = data["data"].get("asia_indices", [])
    asia_label = "亚市开盘预判（基于期货）" if mode == "morning" else "亚市收盘行情"
    asia_rows = "".join(build_ticker_row(t) for t in asia_indices)

    australia_indices = data["data"].get("australia_indices", [])
    australia_rows = "".join(build_ticker_row(t) for t in australia_indices)

    china_indices = data["data"].get("china_indices", [])
    china_rows = "".join(build_ticker_row(t) for t in china_indices)

    us_stocks = data["data"].get("us_stocks", [])
    stock_rows = "".join(build_ticker_row(t, show_volume=True, show_cost=True) for t in us_stocks)

    etf = data["data"].get("etf_commodities", [])
    etf_rows = "".join(build_ticker_row(t, show_cost=True) for t in etf)

    commodities = data["data"].get("commodities_spot", [])
    commodity_rows = "".join(build_ticker_row(t) for t in commodities)

    forex = data["data"].get("forex", [])
    forex_rows = "".join(build_ticker_row(t) for t in forex)

    bonds = data["data"].get("bonds", [])
    bond_rows = "".join(build_ticker_row(t) for t in bonds)
    spread_data = data["data"].get("yield_spread", {})
    spread_html = ""
    if spread_data:
        spread_cls = "down" if spread_data.get("10Y_minus_2Y", 0) < 0 else "neutral"
        spread_html = f"""
        <tr>
            <td><span class="symbol">利差</span> <span class="name-label">10Y - 2Y Spread</span></td>
            <td class="{spread_cls} price">{spread_data.get('10Y_minus_2Y', 0):+.3f}%</td>
            <td colspan="2" class="{spread_cls}">{spread_data.get('status', '')}</td>
        </tr>"""

    sg_funds = data["data"].get("sg_funds", [])
    sg_fund_rows = ""
    for f in sg_funds:
        nav = f.get("nav")
        nav_str = f"{nav:.4f}" if nav else "─"
        nav_date = f.get("nav_date") or "待更新"
        sg_fund_rows += f"""
        <tr>
            <td><span class="name-label">{f['short']}</span></td>
            <td class="price neutral">{nav_str}</td>
            <td class="neutral" colspan="2">{nav_date} | {f.get('note','')}</td>
        </tr>"""

    news_by_category = {}
    all_news_sorted = []
    if news_data:
        standard_cats = ["Breaking", "Market", "Central Bank", "Geopolitics",
                         "Commodities", "Earnings", "FX", "General"]

        if isinstance(news_data, dict):
            all_news_sorted = news_data.get("all_news", [])
            raw_by_cat = news_data.get("by_category", {})
            if raw_by_cat and isinstance(next(iter(raw_by_cat.values()), None), list):
                news_by_category = raw_by_cat
            else:
                for item in all_news_sorted:
                    raw_cat = item.get("category", "General")
                    matched = "General"
                    for sc in standard_cats:
                        if sc.lower() in raw_cat.lower():
                            matched = sc
                            break
                    news_by_category.setdefault(matched, []).append(item)
        elif isinstance(news_data, list) and len(news_data) > 0:
            all_news_sorted = news_data
            for item in news_data:
                raw_cat = item.get("category", "General")
                matched = "General"
                for sc in standard_cats:
                    if sc.lower() in raw_cat.lower():
                        matched = sc
                        break
                news_by_category.setdefault(matched, []).append(item)

    category_icons = {
        "Breaking": "🔥", "Market": "💼", "Central Bank": "💰",
        "Geopolitics": "🌍", "Commodities": "🛢️", "Earnings": "🏢",
        "FX": "💱", "General": "📊"
    }
    category_names = {
        "Breaking": "突发 Breaking", "Market": "市场 Market",
        "Central Bank": "央行 Central Bank", "Geopolitics": "地缘 Geopolitics",
        "Commodities": "大宗 Commodities", "Earnings": "财报 Earnings",
        "FX": "汇率 FX", "General": "综合 General"
    }

    news_html = ""
    if not all_news_sorted:
        news_html = '<div class="news-placeholder"><span style="color:var(--text-muted);">新闻数据将在自动化运行时通过网络搜索实时获取</span><br><span style="font-size:11px;color:var(--text-muted);">News data will be fetched in real-time via web search during automation</span></div>'
    else:
        for category in news_by_category:
            category_news = news_by_category[category]
            if not category_news:
                continue

            icon = category_icons.get(category, "📰")
            category_name = category_names.get(category, category)
            news_html += '<div class="news-category"><div class="news-category-header">' + icon + ' ' + category_name + '</div>'

            for item in category_news[:5]:
                title = item.get('title', '')
                title_cn = item.get('title_cn', '')
                source = item.get('source', '')
                snippet = item.get('snippet', '')
                snippet_cn = item.get('snippet_cn', '')
                total_score = item.get('total_score') or item.get('score') or 0

                def _has_cjk(s):
                    return bool(re.search(r'[\u4e00-\u9fff]', s or ''))
                if _has_cjk(title):
                    title = ''
                if _has_cjk(snippet):
                    snippet = ''

                score_stars = "⭐" * int(total_score / 2)
                score_class = "score-high" if total_score >= 9 else ("score-medium" if total_score >= 7 else "score-low")
                domain = source.replace('www.', '').split('/')[0] if source and '/' in source else (source or '─')

                title_html = '<div class="news-title">' + title + '</div>' if title else ''
                if title_cn:
                    title_html += '<div class="news-title-cn">' + title_cn + '</div>'

                snippet_html = '<div class="news-snippet">' + snippet + '</div>' if snippet else ''
                if snippet_cn:
                    snippet_html += '<div class="news-snippet-cn">' + snippet_cn + '</div>'

                news_html += '<div class="news-item"><div class="news-meta"><span class="news-domain">' + domain + '</span><span class="news-score ' + score_class + '" title="权威评分 Authority Score: ' + str(total_score) + '/10">' + score_stars + '</span></div>' + title_html + snippet_html + '</div>'

            news_html += '</div>'

    ICON_DEFAULT = {"green": "🟢", "yellow": "🟡", "red": "🔴"}

    summary_items = []
    market_summary_text = (insights or {}).get("market_summary", "")
    if market_summary_text:
        summary_items.append(("🟡", "yellow", market_summary_text))
    key_themes = (insights or {}).get("key_themes", [])
    if key_themes:
        for theme in key_themes:
            if isinstance(theme, str):
                emoji = theme[0] if theme and ord(theme[0]) > 127 else "📌"
                summary_items.append((emoji, "yellow", theme))
            elif isinstance(theme, dict):
                summary_items.append((
                    theme.get("icon") or "📌",
                    theme.get("level", "yellow"),
                    theme.get("text", str(theme))
                ))
    old_summary = (insights or {}).get("summary", [])
    if old_summary and not key_themes and not market_summary_text:
        for item in old_summary:
            summary_items.append((
                item.get("icon") or ICON_DEFAULT.get(item.get("level", "yellow"), "🟡"),
                item.get("level", "yellow"),
                item.get("text", "")
            ))

    if summary_items:
        summary_html = ""
        for icon, level, text in summary_items:
            box_class = "summary-box" + (" green" if level == "green" else " red" if level == "red" else "")
            summary_html += f'<div class="{box_class}"><span class="summary-icon">{icon}</span><span class="summary-text">{text}</span></div>'
    else:
        summary_html = '<div class="summary-box"><span class="summary-icon">🟡</span><span class="summary-text">执行摘要数据未提供，请通过 --insights 参数传入 AI 生成的分析内容。</span></div>'

    portfolio_insights = (insights or {}).get("portfolio_insights", {}) or (insights or {}).get("stock_comments", {})
    if isinstance(portfolio_insights, list):
        portfolio_insights = {item.get("symbol", ""): item.get("comment", "") for item in portfolio_insights if isinstance(item, dict)}
    if portfolio_insights:
        portfolio_rows_html = ""
        for symbol, note in portfolio_insights.items():
            portfolio_rows_html += f'<div class="news-item"><div class="news-meta"><span class="news-domain">{symbol}</span></div><div class="news-title"><a href="#">{note}</a></div></div>'
        portfolio_insights_html = f'''
    <div class="card">
        <div class="card-title">💼 持仓个股分析 Portfolio Insights</div>
        {portfolio_rows_html}
    </div>'''
    else:
        portfolio_insights_html = ""

    watch_points = (insights or {}).get("watch_points_today", [])
    risk_alerts  = (insights or {}).get("risk_alerts", [])
    action_items = (insights or {}).get("actions", [])
    risk_items   = (insights or {}).get("risks", [])
    investment_insights = (insights or {}).get("investment_insights", [])

    if watch_points or risk_alerts or action_items or risk_items or investment_insights:
        insights_html = ""
        for pt in watch_points:
            text = pt.get("text", str(pt)) if isinstance(pt, dict) else str(pt)
            insights_html += f'<div class="summary-box"><span class="summary-icon">📌</span><span class="summary-text"><strong>今日关注：</strong>{text}</span></div>'
        for item in action_items:
            insights_html += f'<div class="summary-box"><span class="summary-icon">📌</span><span class="summary-text"><strong>短期操作提示：</strong>{item["text"]}</span></div>'
        for alert in risk_alerts:
            text = alert.get("text", str(alert)) if isinstance(alert, dict) else str(alert)
            insights_html += f'<div class="summary-box red"><span class="summary-icon">⚠️</span><span class="summary-text"><strong>风险提示：</strong>{text}</span></div>'
        for item in risk_items:
            insights_html += f'<div class="summary-box red"><span class="summary-icon">⚠️</span><span class="summary-text"><strong>风险提示：</strong>{item["text"]}</span></div>'
        for item in investment_insights:
            if isinstance(item, dict):
                theme = item.get("theme", "")
                text = item.get("insight", "")
                insights_html += f'<div class="summary-box"><span class="summary-icon">📌</span><span class="summary-text"><strong>{theme}</strong>｜{text}</span></div>'
    else:
        insights_html = '<div class="summary-box"><span class="summary-icon">📌</span><span class="summary-text"><strong>短期操作提示：</strong>投资建议数据未提供，请通过 --insights 参数传入 AI 生成的分析内容。</span></div>'

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>投资日报 {date_str} {report_type}</title>
    <style>
        :root {{
            --up: #16a34a;
            --down: #dc2626;
            --neutral: #94a3b8;
            --bg: #0f172a;
            --card: #1e293b;
            --border: #334155;
            --text: #f1f5f9;
            --text-muted: #94a3b8;
            --accent: #38bdf8;
            --warn-high: #ef4444;
            --warn-mid: #f59e0b;
            --warn-low: #22c55e;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ background: var(--bg); color: var(--text); font-family: -apple-system, 'PingFang SC', 'Microsoft YaHei', sans-serif; font-size: 14px; line-height: 1.6; }}
        .container {{ max-width: 1200px; margin: 0 auto; padding: 20px; }}
        .report-header {{ background: linear-gradient(135deg, #1e3a5f, #0f172a); border: 1px solid var(--border); border-radius: 12px; padding: 24px 32px; margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center; }}
        .report-title {{ font-size: 22px; font-weight: 700; color: var(--accent); }}
        .report-subtitle {{ color: var(--text-muted); font-size: 13px; margin-top: 4px; }}
        .report-meta {{ text-align: right; color: var(--text-muted); font-size: 12px; }}
        .report-type-badge {{ display: inline-block; background: var(--accent); color: #0f172a; font-weight: 700; padding: 4px 12px; border-radius: 20px; font-size: 13px; margin-bottom: 6px; }}
        .card {{ background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 20px; margin-bottom: 16px; }}
        .card-title {{ font-size: 15px; font-weight: 600; color: var(--accent); margin-bottom: 16px; border-bottom: 1px solid var(--border); padding-bottom: 8px; }}
        .grid-2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
        .grid-3 {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 16px; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th {{ color: var(--text-muted); font-weight: 500; text-align: left; padding: 6px 10px; font-size: 12px; border-bottom: 1px solid var(--border); }}
        td {{ padding: 8px 10px; border-bottom: 1px solid rgba(51,65,85,0.4); }}
        .ticker-row:hover {{ background: rgba(56,189,248,0.05); }}
        .symbol {{ font-weight: 700; color: var(--accent); font-family: monospace; font-size: 13px; }}
        .name-label {{ color: var(--text-muted); font-size: 12px; }}
        .price {{ font-weight: 600; }}
        .volume {{ color: var(--text-muted); font-size: 12px; }}
        .change-abs {{ font-size: 12px; }}
        .cost-col {{ font-size: 12px; }}
        .cost-price {{ color: var(--text-muted); font-family: monospace; }}
        .cost-pl {{ font-size: 11px; font-weight: 600; }}
        .up {{ color: var(--up); }}
        .down {{ color: var(--down); }}
        .neutral {{ color: var(--neutral); }}
        .error-row {{ opacity: 0.5; }}
        .vix-badge {{ display: inline-block; padding: 4px 12px; border-radius: 6px; font-size: 12px; font-weight: 600; background: rgba(148,163,184,0.15); margin-left: 12px; }}
        .vix-badge.up {{ background: rgba(220,38,38,0.15); color: var(--down); }}
        .vix-label {{ font-weight: 400; }}
        .news-item {{ border-left: 3px solid var(--border); padding: 10px 14px; margin-bottom: 10px; background: rgba(15,23,42,0.4); border-radius: 0 6px 6px 0; }}
        .news-header {{ display: flex; justify-content: space-between; margin-bottom: 4px; }}
        .news-source {{ color: var(--text-muted); font-size: 11px; }}
        .news-title {{ font-size: 13px; line-height: 1.5; }}
        .news-effect {{ color: var(--text-muted); font-size: 12px; margin-top: 4px; font-style: italic; }}
        .summary-box {{ border-left: 3px solid var(--warn-mid); padding: 10px 14px; background: rgba(245,158,11,0.08); border-radius: 0 6px 6px 0; margin-bottom: 8px; }}
        .summary-box.green {{ border-color: var(--warn-low); background: rgba(34,197,94,0.08); }}
        .summary-box.red {{ border-color: var(--warn-high); background: rgba(239,68,68,0.08); }}
        .summary-icon {{ font-size: 16px; margin-right: 8px; }}
        .summary-text {{ font-size: 13px; line-height: 1.6; }}
        .report-footer {{ text-align: center; color: var(--text-muted); font-size: 11px; margin-top: 24px; padding-top: 16px; border-top: 1px solid var(--border); }}
        @media (max-width: 768px) {{
            .grid-2, .grid-3 {{ grid-template-columns: 1fr; }}
            .report-header {{ flex-direction: column; gap: 12px; }}
            .report-meta {{ text-align: left; }}
        }}
        .news-placeholder {{ text-align: center; padding: 30px; color: var(--text-muted); }}
        .news-category {{ margin-bottom: 20px; border-bottom: 1px solid #374151; padding-bottom: 16px; }}
        .news-category:last-child {{ border-bottom: none; margin-bottom: 0; padding-bottom: 0; }}
        .news-category-header {{ font-size: 13px; font-weight: 600; color: var(--text-primary); margin-bottom: 12px; padding: 4px 8px; background: rgba(255,255,255,0.05); border-radius: 4px; display: inline-block; }}
        .news-item {{ margin-bottom: 14px; padding-left: 12px; border-left: 2px solid var(--neutral); }}
        .news-meta {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px; }}
        .news-domain {{ font-size: 11px; color: var(--text-muted); font-style: italic; }}
        .news-score {{ font-size: 11px; font-weight: 600; }}
        .score-high {{ color: #16a34a; }}
        .score-medium {{ color: #eab308; }}
        .score-low {{ color: #dc2626; }}
        .news-title {{ font-size: 13px; font-weight: 500; color: var(--text); line-height: 1.4; margin-bottom: 4px; }}
        .news-title-cn {{ font-size: 13px; font-weight: 400; color: #fde68a; line-height: 1.4; margin-bottom: 4px; }}
        .news-title a {{ color: var(--text); text-decoration: none; }}
        .news-snippet {{ font-size: 11px; color: var(--text-muted); line-height: 1.4; }}
        .news-snippet-cn {{ font-size: 11px; color: var(--text-muted); line-height: 1.4; font-style: italic; }}
    </style>
</head>
<body>
<div class="container">

    <!-- Header -->
    <div class="report-header">
        <div>
            <div class="report-title">📊 每日投资报告</div>
            <div class="report-subtitle">{date_str} {weekday} &nbsp;|&nbsp; {report_subtitle}</div>
        </div>
        <div class="report-meta">
            <div class="report-type-badge">{report_type}</div>
            <div>数据更新 Data Updated: {generated_at}</div>
            <div>数据来源 Data Sources: Yahoo Finance</div>
        </div>
    </div>

    <!-- Section 0: 重要新闻 Key News -->
    <div class="card">
        <div class="card-title">📰 重要新闻 Key News</div>
        {news_html}
    </div>

    <!-- Section 1: 执行摘要 Executive Summary -->
    <div class="card">
        <div class="card-title">⚡ 执行摘要 Executive Summary</div>
        {summary_html}
    </div>

    <!-- Section 2: 全球市场行情 Global Market Overview -->

    <!-- 第一行：美股 + 欧洲 -->
    <div class="grid-2">
        <div class="card">
            <div class="card-title">🇺🇸 美股指数 US Markets {vix_html}</div>
            <table>
                <thead><tr><th>指数 Index</th><th>收盘价 Close</th><th>涨跌幅 Change%</th><th>变动 Change</th></tr></thead>
                <tbody>{us_index_rows}</tbody>
            </table>
        </div>
        <div class="card">
            <div class="card-title">🇪🇺 欧洲市场 European Markets</div>
            <table>
                <thead><tr><th>市场 Market</th><th>指数 Index</th><th>涨跌幅 Change%</th><th>变动 Change</th></tr></thead>
                <tbody>{europe_rows}</tbody>
            </table>
        </div>
    </div>

    <!-- 第二行：亚洲 + 澳洲&中国 -->
    <div class="grid-2">
        <div class="card">
            <div class="card-title">🌏 亚洲市场 Asia Markets
                <span style="font-size:11px;color:var(--text-muted);font-weight:400;margin-left:8px;">{asia_label}</span>
            </div>
            <table>
                <thead><tr><th>市场 Market</th><th>指数 Index</th><th>涨跌幅 Change%</th><th>变动 Change</th></tr></thead>
                <tbody>{asia_rows}</tbody>
            </table>
        </div>
        <div class="card">
            <div class="card-title">🌏 澳洲 & 中国市场 Australia & China</div>
            <table>
                <thead><tr><th>市场 Market</th><th>指数 Index</th><th>涨跌幅 Change%</th><th>变动 Change</th></tr></thead>
                <tbody>
                    <tr><td colspan="4" style="color:var(--text-muted);font-size:11px;padding:4px 10px;">🇦🇺 澳洲市场 Australia</td></tr>
                    {australia_rows}
                    <tr><td colspan="4" style="color:var(--text-muted);font-size:11px;padding:4px 10px;padding-top:12px;">🇨🇳 中国市场 China A-Share (Reference)</td></tr>
                    {china_rows}
                </tbody>
            </table>
        </div>
    </div>

    <!-- Section 3: 持仓个股 Portfolio Stocks -->
    <div class="card">
        <div class="card-title">📈 持仓个股 Portfolio Stocks</div>
        <table>
            <thead><tr><th>股票 Stock</th><th>现价 Price(USD)</th><th>成本价 Cost Basis</th><th>涨跌幅 Change%</th><th>变动 Change</th><th>成交量 Volume</th></tr></thead>
            <tbody>{stock_rows}</tbody>
        </table>
    </div>

    <!-- Section 4: ETF & 贵金属 ETF & Precious Metals -->
    <div class="grid-2">
        <div class="card">
        <div class="card-title">🥇 ETF & 贵金属 ETF & Precious Metals</div>
            <table>
                <thead><tr><th>标的 Ticker</th><th>现价 Price</th><th>成本价 Cost</th><th>涨跌幅 Change%</th><th>变动 Change</th></tr></thead>
                <tbody>{etf_rows}{commodity_rows}</tbody>
            </table>
        </div>

        <!-- 宏观：汇率+债券 -->
        <div class="card">
            <div class="card-title">💱 汇率 & 债券 FX & Bonds</div>
            <table>
                <thead><tr><th>指标 Indicator</th><th>数值 Value</th><th>涨跌幅 Change%</th><th>变动 Change</th></tr></thead>
                <tbody>{forex_rows}{bond_rows}{spread_html}</tbody>
            </table>
        </div>
    </div>

    <!-- 新闻版块已移至顶部 -->

    <!-- Section 5b: 持仓个股分析 Portfolio Insights -->
    {portfolio_insights_html}

    <!-- Section 6: 投资建议 Investment Insights -->
    <div class="card">
        <div class="card-title">💡 投资建议 Investment Insights</div>
        {insights_html}
        <div style="color:var(--text-muted);font-size:11px;margin-top:12px;">
            ⚠️ 本报告仅供参考，不构成投资建议。投资决策请结合个人情况独立判断。
       This report is for reference only and does not constitute investment advice. Make independent decisions based on your own circumstances.
        </div>
    </div>

    <div class="report-footer">
        投资日报 · 每日 08:00 早报 / 20:00 晚报 &nbsp;|&nbsp; 数据来源 Data Sources: Yahoo Finance · Reuters · Bloomberg &nbsp;|&nbsp; 生成时间：{generated_at}
    </div>

</div>
</body>
</html>"""
    return html


def main():
    parser = argparse.ArgumentParser(description="生成HTML投资日报")
    parser.add_argument("--data", default="market_data.json", help="市场数据JSON文件路径")
    parser.add_argument("--mode", choices=["morning", "evening", "full"], default="morning")
    parser.add_argument("--output", default="report.html", help="输出HTML文件路径")
    parser.add_argument("--news", default=None, help="新闻JSON文件路径（可选）")
    parser.add_argument("--insights", default=None, help="执行摘要+投资建议JSON文件路径（可选）")
    args = parser.parse_args()

    with open(args.data, "r", encoding="utf-8") as f:
        data = json.load(f)

    news_data = None
    if args.news and os.path.exists(args.news):
        with open(args.news, "r", encoding="utf-8") as f:
            news_data = json.load(f)

    insights = None
    if args.insights and os.path.exists(args.insights):
        with open(args.insights, "r", encoding="utf-8") as f:
            insights = json.load(f)

    news_items = []
    if isinstance(news_data, dict):
        news_items = news_data.get("all_news", [])
    elif isinstance(news_data, list):
        news_items = news_data
    if news_items:
        missing_en = [i for i, it in enumerate(news_items) if not it.get("snippet")]
        missing_cn = [i for i, it in enumerate(news_items) if not it.get("snippet_cn")]
        if missing_en or missing_cn:
            print(f"⚠️  警告: {len(news_items)} 条新闻中, {len(missing_en)} 条缺英文 snippet / {len(missing_cn)} 条缺中文 snippet_cn", file=sys.stderr)
            print("    字段名必须是 snippet / snippet_cn (不是 summary)。详见 SKILL.md raw_news.json 规范。", file=sys.stderr)
            print(f"    缺失索引 EN: {missing_en}, CN: {missing_cn}", file=sys.stderr)

    html = generate_html_report(data, args.mode, news_data, insights)

    with open(args.output, "w", encoding="utf-8") as f:
        f.write(html)

    if news_items:
        expected = len(news_items)
        rendered_en = html.count('class="news-snippet">')
        rendered_cn = html.count('class="news-snippet-cn">')
        if rendered_en < expected or rendered_cn < expected:
            print(f"⚠️  渲染校验失败: 预期 {expected} 条 snippet, 实际渲染 EN={rendered_en} / CN={rendered_cn}", file=sys.stderr)
            print("    报告已生成但新闻摘要可能显示为空! 请检查 news JSON 的 snippet/snippet_cn 字段。", file=sys.stderr)
        else:
            print(f"✅ 渲染校验通过: {expected} 条新闻摘要 (EN={rendered_en} + CN={rendered_cn}) 全部渲染")

    print(f"✅ HTML报告已生成：{args.output}")


if __name__ == "__main__":
    main()
