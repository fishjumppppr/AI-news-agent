from __future__ import annotations

import argparse
import logging
from datetime import datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

from .config import load_settings, load_sources
from .fetch import enrich_article_text, fetch_sources
from .filtering import filter_items
from .push import push_webhook
from .report import fallback_report, write_report
from .summarize import build_prompt, summarize_with_litellm


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def setup_logging(log_file: Path) -> None:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


def run() -> Path:
    load_dotenv(PROJECT_ROOT / ".env", override=True)
    settings = load_settings(PROJECT_ROOT / "config" / "settings.yaml")
    sources = load_sources(PROJECT_ROOT / "config" / "sources.yaml")
    tz = ZoneInfo(settings.report.get("timezone", "Asia/Shanghai"))
    now = datetime.now(tz)
    # Report for the day the run happens. lookback_days=N covers the last N
    # calendar days in the configured timezone, ending at the run moment.
    lookback_days = max(1, settings.lookback_days)
    report_date = now.date().isoformat()
    window_start = datetime.combine(now.date(), time.min, tzinfo=tz) - timedelta(
        days=lookback_days - 1
    )
    window_end = now

    setup_logging(PROJECT_ROOT / "logs" / "agent.log")
    logging.info("starting AI news run for report_date=%s", report_date)

    raw_items = fetch_sources(sources, settings)
    logging.info("fetched %s raw items from %s sources", len(raw_items), len(sources))

    filtered = filter_items(
        raw_items,
        window_start=window_start,
        window_end=window_end,
        keywords=settings.keywords,
        max_items=settings.max_items,
    )
    logging.info("kept %s filtered items", len(filtered))

    enriched = []
    for index, item in enumerate(filtered):
        if index < settings.max_enriched_items and not item.title.startswith("[抓取失败]"):
            enriched.append(enrich_article_text(item, settings))
        else:
            enriched.append(item)
    prompt = build_prompt(enriched, report_date)
    try:
        content = summarize_with_litellm(prompt)
    except Exception as exc:
        logging.exception("summary failed")
        content = fallback_report(enriched, report_date, exc)

    path = write_report(PROJECT_ROOT / "data" / "reports", report_date, content)
    logging.info("wrote report: %s", path)
    pushed_to = push_webhook(content, path)
    if pushed_to:
        logging.info("pushed report to webhook: %s", pushed_to)
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch and summarize AI/Agent news.")
    parser.add_argument("--once", action="store_true", help="Run once and exit.")
    args = parser.parse_args()
    if args.once:
        print(run())
    else:
        print(run())


if __name__ == "__main__":
    main()
