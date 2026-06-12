from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "journals.yml"
DEFAULT_EXCEL_PATH = DATA_DIR / "paper_database.xlsx"
DEFAULT_MARKDOWN_PATH = DATA_DIR / "paper_database.md"


@dataclass(frozen=True)
class JournalConfig:
    id: str
    name: str
    group: str
    issns: tuple[str, ...]
    aliases: tuple[str, ...]


@dataclass(frozen=True)
class Settings:
    slack_webhook_url: str | None
    slack_channel: str | None
    slack_username: str
    slack_icon_emoji: str
    timezone: str
    search_rows_per_journal: int


def load_settings() -> Settings:
    load_dotenv(PROJECT_ROOT / ".env")

    import os

    return Settings(
        slack_webhook_url=os.getenv("SLACK_WEBHOOK_URL") or None,
        slack_channel=os.getenv("SLACK_CHANNEL") or None,
        slack_username=os.getenv("SLACK_USERNAME", "paper-alert-bot"),
        slack_icon_emoji=os.getenv("SLACK_ICON_EMOJI", ":newspaper:"),
        timezone=os.getenv("PAPER_ALERT_TIMEZONE", "Asia/Seoul"),
        search_rows_per_journal=int(os.getenv("PAPER_ALERT_ROWS_PER_JOURNAL", "100")),
    )


def load_journals(path: Path = DEFAULT_CONFIG_PATH) -> list[JournalConfig]:
    with path.open("r", encoding="utf-8") as f:
        raw: dict[str, Any] = yaml.safe_load(f) or {}

    journals: list[JournalConfig] = []
    for item in raw.get("journals", []):
        journals.append(
            JournalConfig(
                id=str(item["id"]),
                name=str(item["name"]),
                group=str(item.get("group", "")),
                issns=tuple(str(v) for v in item.get("issns", [])),
                aliases=tuple(str(v) for v in item.get("aliases", [item["name"]])),
            )
        )
    return journals

