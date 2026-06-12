from __future__ import annotations

from datetime import date, timedelta

from .config import DEFAULT_EXCEL_PATH, DEFAULT_MARKDOWN_PATH, load_journals, load_settings
from .search import search_papers
from .slack import send_slack_alert
from .store import append_papers


def run_daily_job(
    days_back: int = 1,
    no_slack: bool = False,
    from_date: date | None = None,
    to_date: date | None = None,
    max_rows_per_journal: int | None = None,
) -> tuple[int, int]:
    settings = load_settings()
    journals = load_journals()
    today = date.today()
    to_date = to_date or today
    from_date = from_date or (to_date - timedelta(days=days_back))

    found = search_papers(
        journals=journals,
        from_date=from_date,
        to_date=to_date,
        rows_per_journal=max_rows_per_journal or settings.search_rows_per_journal,
    )
    added = append_papers(found, DEFAULT_EXCEL_PATH, DEFAULT_MARKDOWN_PATH)
    send_slack_alert(added, settings, dry_run=no_slack)
    return len(found), len(added)
