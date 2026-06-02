"""Command line interface for paper Notion sync."""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

from .notion_api import NotionAPI
from .schemas import build_database_plan, materialize_properties
from .state import load_state, save_state, state_path
from .sync import sync_paper
from .gateway import poll_once


DEFAULT_PAPER_DIR = Path("papers/sp-asym-agentmark-tk")


def get_token() -> str:
    token = os.environ.get("NOTION_TOKEN", "")
    if not token:
        raise SystemExit("NOTION_TOKEN is not set.")
    return token


def resolve_paper_dir(value: str | None) -> Path:
    return (Path(value) if value else DEFAULT_PAPER_DIR).expanduser().resolve()


def cmd_init(args: argparse.Namespace) -> int:
    paper_dir = resolve_paper_dir(args.paper_dir)
    api = NotionAPI(get_token())
    state = load_state(paper_dir)
    state["parent_page_id"] = args.parent_page
    state.setdefault("databases", {})

    database_ids: dict[str, str] = dict(state["databases"])
    for spec in build_database_plan():
        if spec.key in database_ids:
            continue
        props = materialize_properties(spec, database_ids)
        database_ids[spec.key] = api.create_database(args.parent_page, spec.title, props)
        print(f"created {spec.title}: {database_ids[spec.key]}")

    state["databases"] = database_ids
    save_state(paper_dir, state)
    print(f"state saved: {state_path(paper_dir)}")
    return 0


def cmd_sync(args: argparse.Namespace) -> int:
    paper_dir = resolve_paper_dir(args.paper_dir)
    state = load_state(paper_dir)
    if not state.get("databases", {}).get("papers"):
        raise SystemExit("Not initialized. Run init first.")
    api = NotionAPI(get_token())
    summary = sync_paper(api, paper_dir, state, main_tex=args.main_tex)
    save_state(paper_dir, state)
    print(summary)
    return 0


def cmd_tasks(args: argparse.Namespace) -> int:
    paper_dir = resolve_paper_dir(args.paper_dir)
    state = load_state(paper_dir)
    if not state.get("databases", {}).get("agent_tasks"):
        raise SystemExit("Not initialized. Run init first.")
    api = NotionAPI(get_token())
    while True:
        count = poll_once(api, paper_dir, state, main_tex=args.main_tex)
        save_state(paper_dir, state)
        print(f"processed {count} queued task(s)")
        if args.once:
            return 0
        time.sleep(args.interval)


def cmd_status(args: argparse.Namespace) -> int:
    paper_dir = resolve_paper_dir(args.paper_dir)
    state = load_state(paper_dir)
    print(f"paper_dir: {paper_dir}")
    print(f"state: {state_path(paper_dir)}")
    print(f"databases: {', '.join(sorted(state.get('databases', {}).keys())) or '(none)'}")
    print(f"paper_page_id: {state.get('paper_page_id', '') or '(none)'}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="paper-notion-sync")
    parser.add_argument("--paper-dir", default=None, help="Paper directory. Defaults to papers/sp-asym-agentmark-tk.")
    parser.add_argument("--main-tex", default="paper.tex", help="Main LaTeX file.")
    sub = parser.add_subparsers(dest="command", required=True)

    init_parser = sub.add_parser("init", help="Create Notion databases under the parent page.")
    init_parser.add_argument("--parent-page", required=True, help="Notion parent page id for the 'paper iteration' page.")
    init_parser.set_defaults(func=cmd_init)

    sync_parser = sub.add_parser("sync", help="Sync local paper metadata and sections to Notion.")
    sync_parser.set_defaults(func=cmd_sync)

    tasks_parser = sub.add_parser("tasks", help="Poll and execute queued Notion agent tasks.")
    tasks_parser.add_argument("--once", action="store_true", help="Process the queue once and exit.")
    tasks_parser.add_argument("--interval", type=int, default=30, help="Polling interval in seconds.")
    tasks_parser.set_defaults(func=cmd_tasks)

    status_parser = sub.add_parser("status", help="Show local sync state.")
    status_parser.set_defaults(func=cmd_status)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
