# AI / Agent 资讯获取 Agent

这个项目每天抓取 AI / Agent 相关资讯源，调用已有的 LiteLLM 代理生成中文日报，并输出为本地 HTML 文件。日报按**运行当天**的日期命名。

当前版本先做本地文件输出，不启动 LiteLLM 代理。如果配置了 `WEBHOOK_URL`，也会把日报 POST 到对应 webhook。

## 目录

```text
ai_news_agent/        核心代码
config/sources.yaml   RSS/网页源配置
config/settings.yaml  关键词、抓取数量、时区等配置
data/reports/         生成的 HTML 日报和原始 Markdown
logs/                 运行日志
scheduler/            cron 和 macOS launchd 示例
scripts/run_once.sh   单次运行脚本
```

## 1. 配置 LiteLLM 代理

```bash
cd AI-news-agent
cp .env.example .env
```

编辑 `.env`：

```dotenv
LITELLM_BASE_URL=http://127.0.0.1:4000
LITELLM_API_KEY=sk-your-litellm-proxy-key
LITELLM_MODEL=your-litellm-model-name
WEBHOOK_URL=
```

如果 LiteLLM 代理部署在 VPS 上，把 `LITELLM_BASE_URL` 改成你的 HTTPS 地址。
`LITELLM_BASE_URL` 可以写根地址，也可以写到 `/v1`，程序会自动拼接正确的 chat completions 路径。
模型名要使用代理允许的名称；不同 LiteLLM 代理暴露的模型名可能不同，请以你的代理后台或 `/models` 返回为准。

可以先运行 LiteLLM 连通性测试：

```bash
.venv/bin/python -m pytest -s tests/test_litellm_connection.py
```

Webhook 请求体：

```json
{
  "title": "2026-09-17",
  "text": "Markdown 日报内容",
  "html": "<!doctype html>...",
  "report_path": "/absolute/path/to/AI-news-agent/data/reports/2026-09-17.html"
}
```

## 2. 单次运行

```bash
./scripts/run_once.sh
```

生成结果按运行当天日期命名，写入：

```text
data/reports/YYYY-MM-DD.html
```

`YYYY-MM-DD` 是运行当天的日期（时区取 `config/settings.yaml` 里的 `report.timezone`，默认 `Asia/Shanghai`）。抓取窗口默认是「运行当天 00:00 → 本次运行时刻」；如果 `lookback_days` 设为 N，窗口起点再向前多覆盖 N-1 天。

同时会保留一份同名 `.md`，方便调试模型原始输出。

运行日志会写入：

```text
logs/agent.log
```

如果 LiteLLM 不可用，程序仍会输出一份 fallback HTML，包含已抓取的候选资讯和错误原因。

## 3. macOS 定时运行

加载示例 plist：

```bash
PROJECT_DIR="$(pwd)"
sed "s#__PROJECT_DIR__#${PROJECT_DIR}#g" scheduler/com.example.ai-news-agent.plist.template > ~/Library/LaunchAgents/com.example.ai-news-agent.plist
launchctl load ~/Library/LaunchAgents/com.example.ai-news-agent.plist
```

默认每天 08:00 运行。

停止：

```bash
launchctl unload ~/Library/LaunchAgents/com.example.ai-news-agent.plist
```

## 4. Linux / VPS 定时运行

打开 crontab：

```bash
crontab -e
```

添加：

```cron
0 8 * * * /absolute/path/to/AI-news-agent/scripts/run_once.sh >> /absolute/path/to/AI-news-agent/logs/cron.log 2>&1
```

如果部署到 VPS，请把路径改成服务器上的项目路径。

## 当前资讯来源

全部来源定义在 `config/sources.yaml`，当前共 **15 个**，分为官方源、社区源和搜索/API 源：

| 来源 | 类型 | 权重 | 地址/接口 |
| --- | --- | --- | --- |
| OpenAI News | rss | 5 | https://openai.com/news/rss.xml |
| Anthropic News | html | 5 | https://www.anthropic.com/news |
| Google DeepMind Blog | rss | 5 | https://deepmind.google/blog/rss.xml |
| Google AI Blog | rss | 4 | https://blog.google/technology/ai/rss/ |
| Microsoft Azure Blog | rss | 4 | https://azure.microsoft.com/en-us/blog/feed/ |
| Meta AI Blog | html | 4 | https://ai.meta.com/blog/ |
| NVIDIA Blog - AI | rss | 3 | https://blogs.nvidia.com/blog/category/deep-learning/feed/ |
| Hugging Face Blog | rss | 4 | https://huggingface.co/blog/feed.xml |
| arXiv cs.AI | rss | 3 | https://export.arxiv.org/rss/cs.AI |
| arXiv cs.CL | rss | 3 | https://export.arxiv.org/rss/cs.CL |
| GitHub Trending Python | html | 2 | https://github.com/trending/python?since=daily |
| Google News - AI Agents | google_news_rss | 3 | Google News RSS search |
| GDELT - AI Agents | gdelt | 2 | https://api.gdeltproject.org/api/v2/doc/doc |
| Hacker News - AI Agents | hackernews | 2 | https://hn.algolia.com/api/v1/search_by_date |
| GitHub Search - Agent Projects | github_search | 2 | https://api.github.com/search/repositories |

说明：

- `rss`：用 feedparser 直接解析 RSS/Atom。
- `html`：抓列表页再抽取文章链接；GitHub Trending 有单独适配器（解析 `article.Box-row`），取出仓库名和简介。
- `google_news_rss`：用 Google News RSS 搜索补充官方源之外的新闻报道。
- `gdelt`：用 GDELT Doc API 搜索全球新闻；该接口有频率限制，遇到 429 会跳过本次来源。
- `hackernews`：用 Hacker News Algolia API 搜索社区讨论和 Show HN/Launch HN 项目。
- `github_search`：用 GitHub Search API 搜索近期更新的 AI/LLM agent 项目。
- `weight`：只影响候选排序（权重高的排前面），不改变抓取范围。
- 抓取结果只是候选，还要过 `config/settings.yaml` 的日期窗口（`lookback_days`）和 `keywords` 过滤；标题、摘要、正文都不含关键词的条目会被丢弃。
- 为避免日报被单一来源刷屏，候选池会按 `max_items_per_source` 和 `max_items_per_source_type` 做配额控制；宁可少给候选，也不让 GitHub 或 Google News 这类单类来源占满日报。
- Bing News Search 需要 Azure API key，`.env.example` 已预留 `BING_NEWS_API_KEY`，默认未启用。

## 5. 修改来源

编辑：

```text
config/sources.yaml
```

可以增删 RSS 源。GitHub Trending 目前用 HTML 抽取，其它普通网页后续可以继续加适配器。

## 6. 迁移到新机器或 VPS

```bash
git clone git@github.com:fishjumppppr/AI-news-agent.git
cd AI-news-agent
cp .env.example .env
```

然后编辑 `.env`，填入新环境的 `LITELLM_BASE_URL`、`LITELLM_API_KEY`、`LITELLM_MODEL`。

运行：

```bash
./scripts/run_once.sh
```

项目代码不依赖固定安装路径；只有系统定时任务需要使用该机器上的绝对路径。
