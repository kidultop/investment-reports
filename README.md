# 每日全球投资早报系统 (Daily Investment Morning Brief)

在线报告中心：**[https://kidultop.github.io/investment-reports/](https://kidultop.github.io/investment-reports/)**

---

## 一、系统架构与双保险运行机制

1. **方案 C（主力 · macOS 本地守护）**：
   - 配置文件：`~/Library/LaunchAgents/com.kidult.daily-investment-report.plist`
   - 执行脚本：[`scripts/mac_daily_runner.sh`](./scripts/mac_daily_runner.sh)
   - 触发时间：每周一至周六早间 `08:05 SGT` 自动运行（若 Mac 休眠唤醒后自动补跑）。
2. **方案 A（备用/云端 · GitHub Actions）**：
   - 工作流文件：[`.github/workflows/daily_investment_report.yml`](./.github/workflows/daily_investment_report.yml)
   - 执行脚本：[`scripts/run_cloud_report.py`](./scripts/run_cloud_report.py)
   - 支持定时兜底（`08:15` / `08:45` / `09:15 SGT`）及在 GitHub 网页/手机 App 点击 **Run workflow** 一键强制刷新。
3. **Antigravity AI 技能入口**：
   - 技能定义：`/Users/Kidult/.gemini/config/skills/daily-investment-report/SKILL.md`
   - 镜像脚本目录：`/Users/Kidult/.gemini/config/skills/daily-investment-report/scripts/`（与本仓库 `scripts/` 完全同步）。

---

## 二、多周期历史量化分析引擎（6 大核心维度）

系统严禁仅凭单日涨跌幅（`1D%`）下结论，[`scripts/fetch_market_data.py`](./scripts/fetch_market_data.py) 与 [`scripts/run_cloud_report.py`](./scripts/run_cloud_report.py) 自动拉取过去 **1 个月（20 个交易日）** 历史序列并综合以下 6 个维度生成客观分析：

1. **单日涨跌幅 (`change_pct` / `1D%`)**：反映最新交易日即时表现。
2. **近 5 日累计涨跌幅 (`change_5d_pct` / `5D%`)**：反映周度资金流向与短期趋势。
3. **近 20 日累计涨跌幅 (`change_20d_pct` / `20D%`)**：反映月度中期趋势。
4. **较 20 日高点回撤幅度 (`drawdown_20d_pct`)**：精准识别标的是处于“高位突破”还是“深跌回调通道中的超跌反抽”。
5. **均线支撑与压制 (`ma5` / `ma20`)**：对比现价与 5 日、20 日均线得失，判定 `trend_regime`（`超跌反弹`、`连续回调`、`阶段走弱`、`弱势整理`、`多头强势`、`区间震荡`）。
6. **持仓成本真实浮盈/浮亏 (`COST_BASIS`)**：
   - 区分深度被套水下标的（如 `IBM`、`IAU`、`SKHY`、`SPCX`）、微利保本标的（如 `MSFT`、`VT`）与高浮盈底仓标的（如 `SNDK`、`AMD`、`KO`、`AAPL`、`GOOGL`、`NVDA`），提供针对性的控仓、止盈与成本保卫建议。

---

## 三、核心脚本说明

| 脚本文件 | 职责说明 |
| :--- | :--- |
| [`scripts/fetch_market_data.py`](./scripts/fetch_market_data.py) | 抓取全球指数、大宗商品、美债汇率及 16 只持仓的 1 个月历史数据，计算 1D/5D/20D/高点回撤/MA5/MA20。 |
| [`scripts/run_cloud_report.py`](./scripts/run_cloud_report.py) | 自动化总控引擎：协调行情抓取、国际权威外媒中英双语新闻翻译、6 维多周期历史量化分析、HTML 渲染与 `index.html` 归档更新。 |
| [`scripts/fetch_news.py`](./scripts/fetch_news.py) | 国际权威财经媒体白名单校验（严禁任何国内或 `.cn` 信源）、权威度评分与去重分类。 |
| [`scripts/generate_report.py`](./scripts/generate_report.py) | 渲染中英双语 HTML 报告（含 5D/20D/回撤形态列、双语新闻对照、16 只持仓详评与投资建议）。 |
| [`scripts/publish_to_github.py`](./scripts/publish_to_github.py) | 动态识别本地与 GitHub Actions 云端路径，自动重建 `index.html` 并推送至 GitHub Pages。 |
| [`scripts/mac_daily_runner.sh`](./scripts/mac_daily_runner.sh) | macOS 本地一键执行与自动提交推送脚本（支持 `--force` 强制重新生成）。 |
