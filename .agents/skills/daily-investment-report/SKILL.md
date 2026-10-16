---
name: daily-investment-report
description: >-
  每日投资早报生成技能（周一至周六 08:00）。当用户请求生成早报、今日投资报告、市场日报或触发每日定时任务时使用。覆盖全球主要市场（美国、欧洲、亚洲、澳洲、中国参考）指数与行情，结合16只持仓配置（NVDA/GOOGL/AAPL/MSFT/AMD/SNDK/IBM/JNJ/KO/PG/SPCX/SKHY 及 ETF: IAU/SLV/EWJ/VT）与新加坡8只基金，综合国际权威财经媒体与通讯社报道，生成中英双语 HTML 投资早报并自动推送到 GitHub Pages (kidultop.github.io/investment-reports)。
---

# Daily Investment Morning Brief Skill (`daily-investment-report`)

## 1. 目的与触发规则

生成**周一至周六每日全球投资早报（Morning Brief）**（周六早报与平日早报格式完全一致，晚报已取消），综合国际权威媒体的金融经济报道（尤其是与持仓配置相关的关键信息），生成 HTML 报告并自动发布到 GitHub Pages（`https://kidultop.github.io/investment-reports/`）。

### 【时间校验 — 必须优先执行】
在执行任何数据抓取或搜索前，先检查当前本地时间：
- **早报有效窗口**：当日 `06:00 ~ 11:00`
- 如果当前时间已超过 `11:00`（或早于 `06:00`），且用户未明确要求忽略时间窗口强制生成，请直接输出一行：
  `早报时间窗口已过（当前 HH:MM），跳过本次生成。`
  然后立即停止，不执行任何后续步骤。
- 只有当前时间在 `06:00 ~ 11:00` 之间（或用户要求强制测试），才继续执行下方步骤。

---

## 2. 关注市场与持仓配置范围

详见 [watchlist.md](./references/watchlist.md)，完整清单包括：
- **美国指数**：S&P 500 (`^GSPC`)、NASDAQ (`^IXIC`)、Dow Jones (`^DJI`)、VIX (`^VIX`)
- **欧洲指数**：FTSE 100 (`^FTSE`)、DAX 40 (`^GDAXI`)、CAC 40 (`^FCHI`)、Euro Stoxx 50 (`^STOXX50E`)、SMI (`^SSMI`)
- **亚洲指数**：恒生 (`^HSI`)、日经225 (`^N225`)、KOSPI (`^KS11`)、NIFTY 50 (`^NSEI`)、台湾加权 (`^TWII`)、STI (`^STI`)
- **澳洲指数**：ASX 200 (`^AXJO`)、All Ordinaries (`^AORD`)
- **中国参考指数**：上证综合 (`000001.SS`)、深证成分 (`399001.SZ`)、沪深300 (`000300.SS`)、科创50 (`000688.SS`)
- **16只核心持仓（个股 + ETF，含买入成本价）**：
  - 个股（12只）：`NVDA` (184.463)、`GOOGL` (244.70)、`AAPL` (257.397)、`MSFT` (515.00)、`AMD` (180.19)、`SNDK` (205.33)、`IBM` (305.022)、`JNJ` (229.313)、`KO` (66.19)、`PG` (150.81)、`SPCX` (151.65)、`SKHY` (152.00)
  - ETF（4只）：`IAU` (88.95)、`SLV` (44.268)、`EWJ` (83.418)、`VT` (154.322)
- **新加坡基金（8只）**：`AB Low Vol`、`BGF Multi-Asset`、`Infinity Global`、`Infinity US500`、`LionGlobal Japan`、`LionGlobal SG Div`、`LionGlobal SG Trust`、`PIMCO Income`
- **宏观与大宗商品**：`DXY`、`USD/JPY`、`USD/SGD`、`USD/CNY`、`USD/KRW`、`USD/TWD`、美债10Y/2Y及利差、黄金/白银/布伦特原油/WTI原油/铜

---

## 3. 标准执行步骤

脚本所在目录：`SKILL_DIR="/Users/Kidult/.gemini/config/skills/daily-investment-report"`

### Step 1：抓取市场数据与核验

运行 [fetch_market_data.py](./scripts/fetch_market_data.py)：

```bash
python3 /Users/Kidult/.gemini/config/skills/daily-investment-report/scripts/fetch_market_data.py \
  --mode morning \
  --output /tmp/market_data_YYYYMMDD.json
```

#### 关键数据质量复核（必做）：
1. **欧股/部分亚指 `prev_close` 滞后检查**：
   - 将本份 JSON 每个指数的 `prev_close` 与上一份报告（`/Users/Kidult/investment-reports/` 下最新报告）里该指数的 `price` 比对，若不相等说明 `prev_close` 滞后一日导致涨跌幅变成两日累计。
   - 若发现滞后，通过权威收盘综述核实真实单日涨跌幅并修正 JSON 中的 `prev_close`、`change_pct` 和 `change`。
2. **`^IRX` 与真实美债 2Y 收益率修正**：
   - `^IRX` 实为 13 周国库券贴现率，抓取后结合搜索到的美国 2 年期国债真实收益率修正 `bonds` 中的 `US 2Y Treasury` 及 `yield_spread`（`10Y_minus_2Y`）。
3. **期货换月/陈旧报价检查**：
   - 检查 `BZ=F`、`CL=F`、`GC=F`、`SI=F` 是否与隔夜路透/彭博大宗商品结算价综述一致，如有偏差以权威结算价覆盖。

---

### Step 2：搜索国际权威金融新闻 & 持仓相关动态 → 翻译 → 评分分类

使用 `search_web` 工具搜索隔夜全球金融经济要闻及与持仓配置高度相关的消息。

#### 🔒 新闻源白名单（强制遵守，严禁使用中国境内网络/媒体）
> ⚠️ **【红线要求】严格避免从中国网络获取任何信息**：
> 1. 本报告的所有新闻、宏观解读与行业动态必须 **100% 来自国际主流独立权威媒体与国际通讯社**（如 Reuters、Bloomberg、Financial Times、The Wall Street Journal、The Economist、The New York Times、AP、AFP、Nikkei Asia 等）。
> 2. **绝对禁止**使用任何中国境内媒体、财经门户或自媒体（如东方财富、财联社、华尔街见闻、新浪财经、财新网、第一财经、腾讯、网易、新华网、人民网、环球网等），以及任何以 `.cn` 结尾的网站。若搜索结果包含此类来源，必须直接丢弃。

- **Tier 1（10分）**：`reuters.com`、`bloomberg.com`、`ft.com`、`sec.gov`、`reut.rs`
- **Tier 2（9分）**：`wsj.com`、`economist.com`
- **Tier 3（8分）**：`bbc.com`、`bbc.co.uk`、`afp.com`、`apnews.com`、`federalreserve.gov`、`ecb.europa.eu`、`boj.or.jp`、`mas.gov.sg`、`clevelandfed.org`
- **Tier 4（7分）**：`nytimes.com`、`asia.nikkei.com`、`nikkei.com`、`barrons.com`、`theglobeandmail.com`
- **Tier 5（6分）**：`channelnewsasia.com`、`straitstimes.com`、`marketwatch.com`、`finance.yahoo.com`、`tradingeconomics.com`、`toledoblade.com`、`cnbc.com`、`fortune.com`、`kitco.com`、`oilprice.com`

> **必查要求**：
> 1. 每天的报告至少覆盖 **Reuters、Bloomberg、AP、AFP** 等国际通讯社中的 2 家以上。
> 2. 必须校验新闻时效（不超过 72 小时）。
> 3. **重点搜索与持仓配置相关的消息**：半导体/AI硬件（`NVDA`、`AMD`、`SNDK`、`SKHY`）、云与科技巨头（`GOOGL`、`AAPL`、`MSFT`、`IBM`）、航空航天（`SPCX` SpaceX）、消费防御（`JNJ`、`KO`、`PG`）、贵金属与日本/全球ETF（`IAU`、`SLV`、`EWJ`、`VT`）。

#### 推荐搜索词（用实际日期替换，不加 `site:` 复合过滤）：
1. `US stock market recap [YYYY-MM-DD] S&P500 Nasdaq Dow overnight close Reuters`
2. `Federal Reserve FOMC inflation CPI Treasury yield [本月年份] latest news`
3. `NVIDIA Google Apple Microsoft AMD SK Hynix SanDisk stock news [本月年份]`
4. `SpaceX SPCX Starlink IBM JNJ Coca-Cola P&G stock news [本月年份]`
5. `oil price gold silver geopolitics Middle East [本月年份] Reuters`
6. `Asia Europe markets Nikkei Hang Seng STOXX [YYYY-MM-DD]`

将整理并翻译好的中英双语新闻写入 `/tmp/raw_news_YYYYMMDD_morning.json`（使用带日期的唯一文件名，标准字段为 `title`、`title_cn`、`source`、`snippet`、`snippet_cn`、`url`、`published_time`），然后运行 [fetch_news.py](./scripts/fetch_news.py)：

```bash
python3 /Users/Kidult/.gemini/config/skills/daily-investment-report/scripts/fetch_news.py \
  --input /tmp/raw_news_YYYYMMDD_morning.json \
  --output /tmp/news_data_YYYYMMDD_morning.json
```

> **注意**：每个分类最多渲染 5 条（`generate_report.py` 中 `category_news[:5]`），确保单一分类不超过 5 条，且对于 Tier 5 来源注意在英文 `title`/`snippet` 中自然包含至少 4 个 `RELEVANCE_KEYWORDS` 以通过 5.5 分阈值。

---

### Step 3：生成执行摘要、16只持仓个股分析与投资建议 (`insights_YYYYMMDD.json`)

基于行情数据与新闻，撰写 `/tmp/insights_YYYYMMDD.json`：

```json
{
  "summary": [
    {
      "icon": "📈",
      "level": "green",
      "text": "隔夜市场核心走势与情绪信号（含三大指数表现与VIX水平）"
    },
    {
      "icon": "🏦",
      "level": "yellow",
      "text": "宏观经济数据、央行政策路径及美债/汇率关键变化"
    },
    {
      "icon": "🌍",
      "level": "red",
      "text": "地缘政治、大宗商品或核心持仓板块的重大驱动事件"
    }
  ],
  "portfolio_insights": {
    "NVDA": "结合当日涨跌幅、现价与成本盈亏比及最新行业新闻的1句简评",
    "GOOGL": "...",
    "AAPL": "...",
    "MSFT": "...",
    "AMD": "...",
    "SNDK": "...",
    "IBM": "...",
    "JNJ": "...",
    "KO": "...",
    "PG": "...",
    "VT": "...",
    "SPCX": "...",
    "SKHY": "...",
    "IAU": "...",
    "SLV": "...",
    "EWJ": "..."
  },
  "actions": [
    {
      "text": "针对科技/AI芯片持仓（NVDA/AMD/SNDK/SKHY）及云巨头（MSFT/GOOGL/AAPL/IBM）的具体操作建议"
    },
    {
      "text": "针对贵金属（IAU/SLV）、卫星主题（SPCX）及防御/全球指数仓位（KO/PG/JNJ/EWJ/VT）的配置建议"
    }
  ],
  "risks": [
    {
      "text": "当前最需警惕的宏观/政策/地缘尾部风险 1"
    },
    {
      "text": "当前最需警惕的估值/板块波动或个股特定事件风险 2"
    }
  ]
}
```

> ⚠️ **强制完整性检查**：`portfolio_insights` 和 `actions` 必须覆盖全部 16 只持仓（`NVDA`/`GOOGL`/`AAPL`/`MSFT`/`AMD`/`SNDK`/`IBM`/`JNJ`/`KO`/`PG`/`IAU`/`SLV`/`EWJ`/`SPCX`/`VT`/`SKHY`），尤其注意不要遗漏 `VT`、`SPCX` 和 `SKHY`。

---

### Step 4：生成 HTML 报告并校验

运行 [generate_report.py](./scripts/generate_report.py)：

```bash
python3 /Users/Kidult/.gemini/config/skills/daily-investment-report/scripts/generate_report.py \
  --data /tmp/market_data_YYYYMMDD.json \
  --mode morning \
  --news /tmp/news_data_YYYYMMDD_morning.json \
  --insights /tmp/insights_YYYYMMDD.json \
  --output /tmp/daily_report_YYYYMMDD_morning.html
```

检查脚本输出的渲染校验信息，确认所有新闻的中英文摘要（`EN` / `CN`）均已完整渲染。

---

### Step 5：自动发布到 GitHub Pages

运行 [publish_to_github.py](./scripts/publish_to_github.py)，自动将新报告同步到 `/Users/Kidult/investment-reports`，重建 `index.html` 并推送到 GitHub（支持本地 `git push` 与 `gh api` 自动降级双保险）：

```bash
python3 /Users/Kidult/.gemini/config/skills/daily-investment-report/scripts/publish_to_github.py \
  --report /tmp/daily_report_YYYYMMDD_morning.html
```

发布完成后，在回复中向用户输出：
1. **200 字以内的纯文字执行摘要与今日核心关注点**；
2. **报告本地文件链接与在线访问链接**：
   - 报告列表：`https://kidultop.github.io/investment-reports/`
   - 今日早报：`https://kidultop.github.io/investment-reports/daily_report_YYYYMMDD_morning.html`
