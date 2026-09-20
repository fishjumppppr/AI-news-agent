from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import requests


def push_webhook(content: str, report_path: Path, project_root: Path) -> Optional[str]:
    webhook_url = os.environ.get("WEBHOOK_URL", "").strip()
    if not webhook_url:
        return None
    display_path = report_path.relative_to(project_root)

    response = requests.post(
        webhook_url,
        json={
            "title": report_path.stem,
            "text": content,
            "html": report_path.read_text(encoding="utf-8") if report_path.suffix == ".html" else "",
            "report_path": str(display_path),
        },
        timeout=30,
    )
    response.raise_for_status()
    return webhook_url
