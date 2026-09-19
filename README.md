# AI / Agent 资讯获取 Agent

这个项目每天抓取 AI / Agent 相关资讯源，调用已有的 LiteLLM 代理生成中文日报，并输出为本地 HTML 文件。

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
cd /Users/yiqing.yang4/AI资讯获取
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
/Users/yiqing.yang4/AI资讯获取/.venv/bin/python -m pytest -s tests/test_litellm_connection.py
```

Webhook 请求体：

```json
{
  "title": "2026-09-17",
  "text": "Markdown 日报内容",
  "html": "<!doctype html>...",
  "report_path": "/Users/yiqing.yang4/AI资讯获取/data/reports/2026-09-17.html"
}
```

## 2. 单次运行

```bash
/Users/yiqing.yang4/AI资讯获取/scripts/run_once.sh
```

生成结果会写入：

```text
/Users/yiqing.yang4/AI资讯获取/data/reports/YYYY-MM-DD.html
```

同时会保留一份同名 `.md`，方便调试模型原始输出。

运行日志会写入：

```text
/Users/yiqing.yang4/AI资讯获取/logs/agent.log
```

如果 LiteLLM 不可用，程序仍会输出一份 fallback HTML，包含已抓取的候选资讯和错误原因。

## 3. macOS 定时运行

加载示例 plist：

```bash
cp /Users/yiqing.yang4/AI资讯获取/scheduler/com.yiqing.ai-news-agent.plist ~/Library/LaunchAgents/
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
0 8 * * * /Users/yiqing.yang4/AI资讯获取/scripts/run_once.sh >> /Users/yiqing.yang4/AI资讯获取/logs/cron.log 2>&1
```

如果部署到 VPS，请把路径改成服务器上的项目路径。

## 5. 修改来源

编辑：

```text
config/sources.yaml
```

可以增删 RSS 源。GitHub Trending 目前用 HTML 抽取，其它普通网页后续可以继续加适配器。
