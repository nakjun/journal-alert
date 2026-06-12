from __future__ import annotations

import argparse
from datetime import date

from .config import DEFAULT_EXCEL_PATH, DEFAULT_MARKDOWN_PATH
from .job import run_daily_job
from .scheduler import serve
from .store import refresh_missing_abstracts


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Daily medical imaging AI paper Slack alert.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_once = subparsers.add_parser("run-once", help="Search once, update database, and notify Slack.")
    run_once.add_argument("--days-back", type=int, default=1, help="Search from today minus N days.")
    run_once.add_argument("--from-date", type=_parse_date, help="Inclusive search start date, YYYY-MM-DD.")
    run_once.add_argument("--to-date", type=_parse_date, help="Inclusive search end date, YYYY-MM-DD.")
    run_once.add_argument(
        "--max-rows-per-journal",
        type=int,
        help="Maximum Crossref records to inspect per journal for this run.",
    )
    run_once.add_argument("--no-slack", action="store_true", help="Update files without sending Slack.")

    serve_parser = subparsers.add_parser("serve", help="Run the daily 09:00 scheduler in the foreground.")
    serve_parser.add_argument("--hour", type=int, default=9)
    serve_parser.add_argument("--minute", type=int, default=0)

    refresh_parser = subparsers.add_parser(
        "refresh-abstracts",
        help="Fetch missing abstracts directly from publisher pages and refresh Markdown.",
    )
    refresh_parser.add_argument(
        "--force",
        action="store_true",
        help="Refresh existing abstracts too when the directly fetched version is longer.",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "run-once":
        found_count, added_count = run_daily_job(
            days_back=args.days_back,
            no_slack=args.no_slack,
            from_date=args.from_date,
            to_date=args.to_date,
            max_rows_per_journal=args.max_rows_per_journal,
        )
        print(f"Found {found_count} matching papers. Added {added_count} new records.")
        print(f"Excel: {DEFAULT_EXCEL_PATH}")
        print(f"Markdown: {DEFAULT_MARKDOWN_PATH}")
        return 0

    if args.command == "serve":
        serve(hour=args.hour, minute=args.minute)
        return 0

    if args.command == "refresh-abstracts":
        updated_count = refresh_missing_abstracts(force=args.force)
        print(f"Updated {updated_count} abstracts.")
        print(f"Excel: {DEFAULT_EXCEL_PATH}")
        print(f"Markdown: {DEFAULT_MARKDOWN_PATH}")
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 2


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Date must use YYYY-MM-DD format.") from exc
