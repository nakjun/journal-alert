from __future__ import annotations

import requests

from .config import Settings
from .models import Paper


def send_slack_alert(papers: list[Paper], settings: Settings, dry_run: bool = False) -> None:
    if dry_run:
        return
    if not settings.slack_webhook_url:
        print("SLACK_WEBHOOK_URL is not set. Skipping Slack notification.")
        return

    payload = _build_payload(papers, settings)
    response = requests.post(settings.slack_webhook_url, json=payload, timeout=20)
    response.raise_for_status()


def _build_payload(papers: list[Paper], settings: Settings) -> dict:
    count = len(papers)
    header = f"Daily paper alert: {count} new matching paper{'s' if count != 1 else ''}"
    if count == 0:
        text = "No new papers matched today's journal, modality, and AI-method filters."
    else:
        lines = []
        for paper in papers[:12]:
            link = paper.url or (f"https://doi.org/{paper.doi}" if paper.doi else "")
            title = f"<{link}|{paper.title}>" if link else paper.title
            lines.append(
                f"- {title}\n"
                f"  {paper.journal} | {paper.published_date} | {paper.modality} | {paper.method_family}"
            )
        if count > 12:
            lines.append(f"- ... and {count - 12} more in the Excel/Markdown database.")
        text = "\n".join(lines)

    payload = {
        "username": settings.slack_username,
        "icon_emoji": settings.slack_icon_emoji,
        "text": f"{header}\n{text}",
        "blocks": [
            {"type": "header", "text": {"type": "plain_text", "text": header}},
            {"type": "section", "text": {"type": "mrkdwn", "text": text[:3000]}},
        ],
    }
    if settings.slack_channel:
        payload["channel"] = settings.slack_channel
    return payload

