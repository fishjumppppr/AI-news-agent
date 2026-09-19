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
cd /Users/yangyiqing/AI-news-agent
cp .env.example .env
```

编辑 `.env`：

```dotenv
LITELLM_BASE_URL=http://127.0.0.1:4000
LITELLM_API_KEY=sk-your-litellm-proxy-key
LITELLM_MODEL=deepseek-v4-flash
WEBHOOK_URL=
```

如果 LiteLLM 代理部署在 VPS 上，把 `LITELLM_BASE_URL` 改成你的 HTTPS 地址。
`LITELLM_BASE_URL` 可以写根地址，也可以写到 `/v1`，程序会自动拼接正确的 chat completions 路径。
模型名要使用代理允许的名称；例如你的代理可用 `deepseek-v4-flash`，不要写成 `openai/deepseek-v4-flash-0731`。

可以先运行 LiteLLM 连通性测试：

```bash
/Users/yangyiqing/AI-news-agent/.venv/bin/python -m pytest -s tests/test_litellm_connection.py
```

Webhook 请求体：

```json
{
  "title": "2026-09-17",
  "text": "Markdown 日报内容",
  "html": "<!doctype html>...",
  "report_path": "/Users/yangyiqing/AI-news-agent/data/reports/2026-09-17.html"
}
```

## 2. 单次运行

```bash
/Users/yangyiqing/AI-news-agent/scripts/run_once.sh
```

生成结果按运行当天日期命名，写入：

```text
/Users/yangyiqing/AI-news-agent/data/reports/YYYY-MM-DD.html
```

`YYYY-MM-DD` 是运行当天的日期（时区取 `config/settings.yaml` 里的 `report.timezone`，默认 `Asia/Shanghai`）。抓取窗口默认是「运行当天 00:00 → 本次运行时刻」；如果 `lookback_days` 设为 N，窗口起点再向前多覆盖 N-1 天。

同时会保留一份同名 `.md`，方便调试模型原始输出。

运行日志会写入：

```text
/Users/yangyiqing/AI-news-agent/logs/agent.log
```

如果 LiteLLM 不可用，程序仍会输出一份 fallback HTML，包含已抓取的候选资讯和错误原因。

## 3. macOS 定时运行

加载示例 plist：

```bash
cp /Users/yangyiqing/AI-news-agent/scheduler/com.yiqing.ai-news-agent.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.yiqing.ai-news-agent.plist
```

默认每天 08:00 运行。

停止：

```bash
launchctl unload ~/Library/LaunchAgents/com.yiqing.ai-news-agent.plist
```

## 4. Linux / VPS 定时运行

打开 crontab：

```bash
crontab -e
```

添加：

```cron
0 8 * * * /Users/yangyiqing/AI-news-agent/scripts/run_once.sh >> /Users/yangyiqing/AI-news-agent/logs/cron.log 2>&1
```

如果部署到 VPS，请把路径改成服务器上的项目路径。

## 当前资讯来源

全部来源定义在 `config/sources.yaml`，当前共 **11 个**：

| 来源 | 类型 | 权重 | 地址 |
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

说明：

- `rss`：用 feedparser 直接解析 RSS/Atom。
- `html`：抓列表页再抽取文章链接；GitHub Trending 有单独适配器（解析 `article.Box-row`），取出仓库名和简介。
- `weight`：只影响候选排序（权重高的排前面），不改变抓取范围。
- 抓取结果只是候选，还要过 `config/settings.yaml` 的日期窗口（`lookback_days`）和 `keywords` 过滤；标题、摘要、正文都不含关键词的条目会被丢弃。
- 已知问题：arXiv 两个源目前返回 200 但 channel 为空（arXiv 侧行为），实际不产出条目，可考虑换成其它 arXiv 订阅地址。

## 5. 修改来源

编辑：

```text
config/sources.yaml
```

可以增删 RSS 源。GitHub Trending 目前用 HTML 抽取，其它普通网页后续可以继续加适配器。
