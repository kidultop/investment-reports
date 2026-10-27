#!/bin/bash
# ==============================================================================
# mac_daily_runner.sh — macOS launchd 本地每日自动生成与发布早报执行脚本
# ==============================================================================

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"
export LANG="en_US.UTF-8"
export LC_ALL="en_US.UTF-8"

REPO_DIR="/Users/Kidult/investment-reports"
cd "$REPO_DIR" || exit 1

# 加载本地 .env（若存在，可配置 GEMINI_API_KEY）
if [ -f "$REPO_DIR/.env" ]; then
    set -a
    source "$REPO_DIR/.env"
    set +a
fi

echo "========================================================================"
echo "⏰ [$(date '+%Y-%m-%d %H:%M:%S')] 启动 macOS 本地早报自动调度任务"
echo "========================================================================"

# 自动清理任何异常残留的 rebase 状态
if [ -d ".git/rebase-merge" ] || [ -d ".git/rebase-apply" ]; then
    echo "⚠️ 检测到残留的 rebase 状态，自动清理..."
    git rebase --abort 2>/dev/null || rm -rf .git/rebase-merge .git/rebase-apply
fi

# 同步远程最新提交，确保包含云端 GitHub Actions 可能已生成的历史报告
git fetch origin main 2>/dev/null
git merge origin/main --no-edit 2>/dev/null || true

# 检测并优先使用带有 yfinance 依赖的 Python 环境
if [ -x "/usr/local/bin/python3.12" ]; then
    PYTHON_EXEC="/usr/local/bin/python3.12"
elif command -v python3.12 &>/dev/null; then
    PYTHON_EXEC="$(command -v python3.12)"
else
    PYTHON_EXEC="python3"
fi

# 执行早报流水线
$PYTHON_EXEC scripts/run_cloud_report.py "$@"

EXIT_CODE=$?
if [ $EXIT_CODE -ne 0 ]; then
    echo "❌ 早报流水线退出异常，状态码: $EXIT_CODE"
    exit $EXIT_CODE
fi

# 检查是否有新报告或脚本变更，若有则提交并推送
git add daily_report_*.html index.html scripts/
if ! git diff --staged --quiet; then
    echo "📦 检测到新生成的早报，开始自动提交并推送到 GitHub..."
    git commit -m "report: $(date +'%Y-%m-%d') 早报 Morning (多周期历史量化版) [mac-automated]"
    if ! git push origin main; then
        echo "⚠️ 推送遇到远端更新，拉取合并并自动解决 index.html 差异..."
        git fetch origin main
        git merge origin/main --no-edit -m "merge: sync remote before pushing report" || {
            $PYTHON_EXEC -c "import sys; sys.path.insert(0, 'scripts'); from publish_to_github import rebuild_index; rebuild_index()"
            git add index.html
            git commit --no-edit || true
        }
        git push origin main
    fi
    echo "🚀 早报已成功发布并同步到 GitHub Pages！"
else
    echo "✨ 当日早报已是最新状态，无需重复提交。"
fi

echo "✅ 任务顺利完成 - [$(date '+%Y-%m-%d %H:%M:%S')]"
