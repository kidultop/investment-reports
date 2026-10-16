#!/usr/bin/env python3
"""
publish_to_github.py
将生成好的投资日报 / AI 简报 HTML 文件推送到 GitHub Pages 仓库
每次报告生成后自动调用，确保网页端始终是最新内容

推送策略（2026-06-04 重构）：
  1. 优先尝试 git push（本地 git 可用时最快）
  2. git push 失败时（sandbox 限制等），自动降级为 GitHub API 上传（via gh CLI）
  3. GitHub API 模式：逐文件上传 + 重建 index.html，无需本地 git 写权限

用法：
  python3 publish_to_github.py --report /tmp/daily_report_20260324_morning.html
  python3 publish_to_github.py --report /tmp/ai_briefing_20260324_morning.html
"""

import argparse
import base64
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

REPO_DIR = Path.home() / "investment-reports"
INDEX_FILE = REPO_DIR / "index.html"
GIT_BIN = "git"
GH_BIN = "/opt/homebrew/bin/gh"
REPO_NAME = "kidultop/investment-reports"


def run(cmd, cwd=None, check=True):
    env = os.environ.copy()
    env["PATH"] = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:" + env.get("PATH", "")
    result = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True, env=env)
    if check and result.returncode != 0:
        print(f"❌ 命令失败: {cmd}")
        print(result.stderr)
        sys.exit(1)
    return result.stdout.strip()


def is_morning(filename):
    return "morning" in filename.lower()


def is_weekly(filename):
    return "weekly" in filename.lower()


def is_ai_briefing(filename):
    return filename.lower().startswith("ai_briefing_")


def format_report_title(filename):
    m = re.search(r'(\d{4})(\d{2})(\d{2})', filename)
    date_str = f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else "未知日期"
    is_am = is_morning(filename)
    is_wk = is_weekly(filename)
    if is_ai_briefing(filename):
        type_str = "AI 早报 AM" if is_am else "AI 晚报 PM"
    elif is_wk:
        type_str = "周报 Weekly"
    else:
        type_str = "早报 Morning" if is_am else "晚报 Evening"
    return date_str, type_str


def get_all_reports():
    """获取仓库中所有报告（投资 + AI 简报），按时间倒序"""
    reports = []
    for f in REPO_DIR.glob("daily_report_*.html"):
        mtime = f.stat().st_mtime
        reports.append((f.name, mtime, "investment"))
    for f in REPO_DIR.glob("ai_briefing_*.html"):
        mtime = f.stat().st_mtime
        reports.append((f.name, mtime, "ai"))
    reports.sort(key=lambda x: x[1], reverse=True)
    return reports


def rebuild_index():
    """重建 index.html 报告列表，同时显示投资报告和 AI 简报两个分区"""
    all_reports = get_all_reports()
    inv_reports = [(f, t) for f, t, kind in all_reports if kind == "investment"]
    ai_reports  = [(f, t) for f, t, kind in all_reports if kind == "ai"]

    def make_card(fname, i=0):
        date_str, type_str = format_report_title(fname)
        is_am = is_morning(fname)
        is_wk = is_weekly(fname)
        is_ai = is_ai_briefing(fname)
        if is_ai:
            badge_class = "badge-ai-morning" if is_am else "badge-ai-evening"
            badge_text  = "AI 早报" if is_am else "AI 晚报"
            icon = "🤖" if is_am else "🌙"
        elif is_wk:
            badge_class = "badge-weekly"
            badge_text  = "周报"
            icon = "📅"
        else:
            badge_class = "badge-morning" if is_am else "badge-evening"
            badge_text  = "早报" if is_am else "晚报"
            icon = "🌅" if is_am else "🌆"
        return f"""
  <a class="report-card" href="{fname}">
    <div class="report-info">
      <span class="report-icon">{icon}</span>
      <div>
        <div class="report-title">{date_str} {type_str}</div>
        <div class="report-meta">{fname}</div>
      </div>
    </div>
    <span class="badge {badge_class}">{badge_text}</span>
  </a>"""

    inv_cards = "".join(make_card(f, i) for i, (f, _) in enumerate(inv_reports))
    ai_cards  = "".join(make_card(f, i) for i, (f, _) in enumerate(ai_reports))

    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    html = f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>每日简报 | Daily Reports & AI Briefing</title>
<style>
  :root {{
    --bg: #0d1117; --card: #161b22; --border: #30363d;
    --text: #e6edf3; --muted: #8b949e; --accent: #58a6ff;
    --green: #3fb950; --red: #f85149;
    --purple: #a78bfa; --purple-dim: #7c3aed;
  }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    background: var(--bg); color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', sans-serif;
    min-height: 100vh; padding: 40px 20px;
  }}
  .container {{ max-width: 900px; margin: 0 auto; }}
  .header {{
    text-align: center; margin-bottom: 40px;
    padding-bottom: 24px; border-bottom: 1px solid var(--border);
  }}
  .header h1 {{ font-size: 26px; font-weight: 600; margin-bottom: 8px; }}
  .header p {{ color: var(--muted); font-size: 14px; }}
  .tabs {{
    display: flex; gap: 0; margin-bottom: 24px;
    border: 1px solid var(--border); border-radius: 8px; overflow: hidden;
  }}
  .tab-btn {{
    flex: 1; padding: 12px; text-align: center; font-size: 14px;
    font-weight: 600; cursor: pointer; background: var(--card);
    color: var(--muted); border: none; transition: all 0.2s;
  }}
  .tab-btn.active-inv {{ background: rgba(88,166,255,0.1); color: var(--accent); }}
  .tab-btn.active-ai  {{ background: rgba(167,139,250,0.1); color: var(--purple); }}
  .section-block {{ display: none; }}
  .section-block.visible {{ display: block; }}
  .section-title {{
    font-size: 13px; font-weight: 600; color: var(--muted);
    text-transform: uppercase; letter-spacing: 0.5px; margin: 0 0 14px;
  }}
  .report-card {{
    display: flex; align-items: center; justify-content: space-between;
    padding: 14px 18px; background: var(--card); border: 1px solid var(--border);
    border-radius: 8px; margin-bottom: 8px; text-decoration: none;
    color: var(--text); transition: border-color 0.2s;
  }}
  .report-card:hover {{ border-color: var(--accent); }}
  .report-card.ai-card:hover {{ border-color: var(--purple); }}
  .report-info {{ display: flex; align-items: center; gap: 12px; }}
  .report-icon {{ font-size: 20px; }}
  .report-title {{ font-size: 14px; font-weight: 500; }}
  .report-meta {{ font-size: 11px; color: var(--muted); margin-top: 2px; }}
  .badge {{ font-size: 11px; font-weight: 600; padding: 3px 8px; border-radius: 4px; }}
  .badge-morning {{ background: rgba(88,166,255,0.15); color: #58a6ff; }}
  .badge-evening {{ background: rgba(63,185,80,0.15); color: #3fb950; }}
  .badge-weekly {{ background: rgba(251,191,36,0.15); color: #fbbf24; }}
  .badge-ai-morning {{ background: rgba(167,139,250,0.15); color: #a78bfa; }}
  .badge-ai-evening {{ background: rgba(124,58,237,0.15); color: #c4b5fd; }}
  .divider {{ border: none; border-top: 1px solid var(--border); margin: 24px 0; }}
  .footer {{ text-align: center; margin-top: 48px; color: var(--muted); font-size: 12px; line-height: 1.8; }}
  .footer a {{ color: var(--accent); text-decoration: none; }}
  .search-box {{ width: 100%; padding: 10px 14px; margin-bottom: 10px; background: var(--card); border: 1px solid var(--border); border-radius: 8px; color: var(--text); font-size: 14px; box-sizing: border-box; }}
  .search-box::placeholder {{ color: var(--muted); }}
  .search-count {{ font-size: 12px; color: var(--muted); margin-bottom: 14px; }}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>📊 每日简报 · Daily Reports &amp; AI Briefing 🤖</h1>
    <p>投资日报 每日 08:00 早报 · 20:00 晚报 &nbsp;·&nbsp; AI 简报 每日 AM/PM 各一期 &nbsp;|&nbsp; 最后更新：{now}</p>
  </div>

  <input class="search-box" id="searchBox" type="text" placeholder="🔍 搜索日期或文件名（如 202607 或 weekly）..." oninput="filterCards()">
  <div class="search-count" id="searchCount"></div>

  <div class="tabs">
    <button class="tab-btn active-inv" onclick="showTab('inv')">📊 投资日报 Investment Reports</button>
    <button class="tab-btn" onclick="showTab('ai')">🤖 AI 技术简报 AI Briefing</button>
  </div>

  <div id="tab-inv" class="section-block visible">
    <div class="section-title">所有投资报告 All Investment Reports</div>
    {inv_cards}
  </div>

  <div id="tab-ai" class="section-block">
    <div class="section-title">所有 AI 简报 All AI Briefings</div>
    {ai_cards if ai_cards else '<p style="color:#8b949e;text-align:center;padding:32px;">暂无 AI 简报 No AI Briefings Yet</p>'}
  </div>

  <hr class="divider">
  <div class="footer">
    <div>📊 投资数据来源：Yahoo Finance · Reuters · Bloomberg &nbsp;|&nbsp; 仅供参考，不构成投资建议</div>
    <div>🤖 AI 简报来源：OpenAI · Anthropic · Google DeepMind · Hugging Face · arXiv · 新华社 · MIT Tech Review</div>
    <div style="margin-top:8px;"><a href="https://kidultop.github.io/investment-reports/">kidultop.github.io/investment-reports</a></div>
  </div>
</div>
<script>
function showTab(tab) {{
  document.getElementById('tab-inv').classList.remove('visible');
  document.getElementById('tab-ai').classList.remove('visible');
  document.getElementById('tab-' + tab).classList.add('visible');
  document.querySelectorAll('.tab-btn').forEach(function(b) {{
    b.classList.remove('active-inv', 'active-ai');
  }});
  if (tab === 'inv') document.querySelectorAll('.tab-btn')[0].classList.add('active-inv');
  else document.querySelectorAll('.tab-btn')[1].classList.add('active-ai');
}}
function filterCards() {{
  var q = document.getElementById('searchBox').value.toLowerCase().trim();
  var shownInv = 0, shownAi = 0;
  document.querySelectorAll('#tab-inv .report-card').forEach(function(c) {{
    var match = q === '' || c.textContent.toLowerCase().indexOf(q) !== -1;
    c.style.display = match ? '' : 'none';
    if (match) shownInv++;
  }});
  document.querySelectorAll('#tab-ai .report-card').forEach(function(c) {{
    var match = q === '' || c.textContent.toLowerCase().indexOf(q) !== -1;
    c.style.display = match ? '' : 'none';
    if (match) shownAi++;
  }});
  var total = shownInv + shownAi;
  var sc = document.getElementById('searchCount');
  sc.textContent = q === '' ? ('共 ' + total + ' 份报告（投资 ' + shownInv + ' · AI ' + shownAi + '）') : ('匹配：投资 ' + shownInv + ' · AI ' + shownAi);
}}
filterCards();
</script>
</body>
</html>"""

    INDEX_FILE.write_text(html, encoding="utf-8")
    print(f"✓ index.html 已更新 — 投资报告：{len(inv_reports)} 份，AI 简报：{len(ai_reports)} 份")


def gh_api(method, endpoint, data=None):
    """调用 GitHub REST API via gh CLI"""
    cmd = [GH_BIN, "api", "-X", method, endpoint]
    if data:
        cmd.extend(["--input", "-"])
    r = subprocess.run(cmd, input=json.dumps(data) if data else None,
                       capture_output=True, text=True, timeout=30)
    try:
        return json.loads(r.stdout) if r.stdout else {}
    except json.JSONDecodeError:
        print(f"  ⚠️ API 响应解析失败: {r.stdout[:200]}")
        return {}


def gh_get_file_sha(path):
    result = gh_api("GET", f"/repos/{REPO_NAME}/contents/{path}?ref=main")
    return result.get("sha")


def gh_upload_file(path, content_bytes, message):
    sha = gh_get_file_sha(path)
    content_b64 = base64.b64encode(content_bytes).decode()
    data = {"message": message, "content": content_b64, "branch": "main"}
    if sha:
        data["sha"] = sha
    result = gh_api("PUT", f"/repos/{REPO_NAME}/contents/{path}", data)
    return "content" in result or "commit" in result


def publish_via_github_api(report_path):
    """降级方案：通过 GitHub API 直接上传文件，绕过本地 git 限制"""
    print("📦 使用 GitHub API 模式上传（降级方案）...")

    with open(report_path, "rb") as f:
        report_content = f.read()

    filename = Path(report_path).name
    date_str, type_str = format_report_title(filename)
    commit_msg = f"report: {date_str} {type_str}"

    print(f"  上传 {filename}...")
    ok = gh_upload_file(filename, report_content, commit_msg)
    if not ok:
        print(f"  ❌ 上传 {filename} 失败")
        return False
    print(f"  ✅ {filename} 上传成功")

    print("  重建 index.html...")
    local_dest = REPO_DIR / filename
    try:
        shutil.copy2(report_path, local_dest)
    except Exception:
        pass

    rebuild_index()
    index_content = INDEX_FILE.read_bytes()
    ok = gh_upload_file("index.html", index_content, f"index: update listing with {date_str} {type_str}")
    if ok:
        print("  ✅ index.html 更新成功")
    else:
        print("  ⚠️ index.html 更新失败，报告文件已上传")

    print("  已上传文件至 main 分支，GitHub Actions 工作流将自动部署站点。")
    print(f"✅ GitHub API 上传完成！")
    print(f"   网址：https://kidultop.github.io/investment-reports/")
    print(f"   报告：https://kidultop.github.io/investment-reports/{filename}")
    return True


def ensure_git_auth():
    """确保 git 使用 gh 管理的 token，并清理 remote URL 中的硬编码 token"""
    run(f"{GH_BIN} auth setup-git --hostname github.com", cwd=REPO_DIR, check=False)
    url = run(f"{GIT_BIN} remote get-url origin", cwd=REPO_DIR, check=False)
    if url and "@" in url and "github.com" in url and any(p in url for p in [":github_pat_", ":ghp_", ":gho_"]):
        clean_url = re.sub(r"https://[^@]+@", "https://", url)
        run(f"{GIT_BIN} remote set-url origin {clean_url}", cwd=REPO_DIR)
        print(f"✓ 已清理 remote URL 中的硬编码 token")


def publish_via_git(report_path):
    """主方案：通过本地 git push 推送"""
    ensure_git_auth()

    st = run(f"{GIT_BIN} status --porcelain=v1 --branch", cwd=REPO_DIR, check=False)
    if any(k in st for k in ["rebase in progress", "MERGE_HEAD", "CHERRY_PICK_HEAD", "You are in the middle"]):
        print("⚠️ 本地 git 处于交互状态（rebase/merge），跳过 git push，降级 API 模式")
        return False

    dest = REPO_DIR / report_path.name
    shutil.copy2(report_path, dest)
    print(f"✓ 报告已复制：{dest.name}")

    rebuild_index()

    date_str, type_str = format_report_title(report_path.name)
    commit_msg = f"report: {date_str} {type_str}"

    run(f"{GIT_BIN} add .", cwd=REPO_DIR)
    result = run(f'{GIT_BIN} commit -m "{commit_msg}"', cwd=REPO_DIR, check=False)
    if "nothing to commit" in result:
        print("ℹ️  没有变更，跳过推送")
        return True

    env = os.environ.copy()
    env["PATH"] = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:" + env.get("PATH", "")

    pull_proc = subprocess.run(
        f"{GIT_BIN} pull --rebase origin main", shell=True, cwd=REPO_DIR,
        capture_output=True, text=True, env=env
    )
    if pull_proc.returncode != 0:
        print(f"⚠️ git pull --rebase 失败：{(pull_proc.stdout + pull_proc.stderr)[:500]}")
        return False

    push_proc = subprocess.run(
        f"{GIT_BIN} push origin main", shell=True, cwd=REPO_DIR,
        capture_output=True, text=True, env=env
    )
    push_output = push_proc.stdout + push_proc.stderr

    if push_proc.returncode == 0:
        print(f"✅ git push 推送成功！")
        print(f"   网址：https://kidultop.github.io/investment-reports/")
        print(f"   报告：https://kidultop.github.io/investment-reports/{report_path.name}")
        return True
    else:
        print(f"⚠️ git push 失败：{push_output[:500]}")
        return False


def main():
    parser = argparse.ArgumentParser(description="推送投资日报 / AI 简报到 GitHub Pages")
    parser.add_argument("--report", required=True, help="HTML 报告文件路径")
    args = parser.parse_args()

    report_path = Path(args.report)
    if not report_path.exists():
        print(f"❌ 报告文件不存在：{report_path}")
        sys.exit(1)

    if not REPO_DIR.exists():
        print(f"❌ 本地仓库不存在：{REPO_DIR}")
        sys.exit(1)

    print("🚀 开始推送到 GitHub Pages...")

    try:
        success = publish_via_git(report_path)
    except Exception as e:
        print(f"⚠️ git push 异常：{e}")
        success = False

    if not success:
        print("\n⬇️  降级为 GitHub API 模式...")
        try:
            success = publish_via_github_api(report_path)
        except Exception as e:
            print(f"❌ GitHub API 上传也失败：{e}")
            sys.exit(1)

    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
