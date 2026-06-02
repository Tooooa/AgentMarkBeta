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
from .page_agent import poll_page_once
from .page_agent import sync_changelog_once
from .text_page import sync_text_page


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
    existing_by_title = api.discover_child_databases(args.parent_page)
    for spec in build_database_plan():
        if spec.key in database_ids:
            continue
        if spec.title in existing_by_title:
            database_ids[spec.key] = existing_by_title[spec.title]
            state["databases"] = database_ids
            save_state(paper_dir, state)
            print(f"found {spec.title}: {database_ids[spec.key]}")
            continue
        props = materialize_properties(spec, database_ids)
        database_ids[spec.key] = api.create_database(args.parent_page, spec.title, props)
        state["databases"] = database_ids
        save_state(paper_dir, state)
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


def cmd_sync_text_page(args: argparse.Namespace) -> int:
    paper_dir = resolve_paper_dir(args.paper_dir)
    api = NotionAPI(get_token())
    summary = sync_text_page(
        api,
        paper_dir,
        parent_page_id=args.parent_page,
        title=args.title,
        main_tex=args.main_tex,
    )
    print(summary)
    return 0


def cmd_page_agent(args: argparse.Namespace) -> int:
    paper_dir = resolve_paper_dir(args.paper_dir)
    api = NotionAPI(get_token())
    while True:
        count = poll_page_once(
            api,
            paper_dir,
            parent_page_id=args.parent_page,
            allow_write=args.write_local,
            commit_changes=args.commit,
            sync_text=args.sync_text,
        )
        print(f"processed {count} pending communication task(s)")
        if args.once:
            return 0
        time.sleep(args.interval)


def cmd_sync_changes(args: argparse.Namespace) -> int:
    paper_dir = resolve_paper_dir(args.paper_dir)
    api = NotionAPI(get_token())
    count = sync_changelog_once(api, paper_dir, parent_page_id=args.parent_page)
    print(f"processed {count} pending changelog item(s)")
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

    text_parser = sub.add_parser("sync-text-page", help="Sync paper body into a child page as readable prose.")
    text_parser.add_argument("--parent-page", required=True, help="Notion parent page id.")
    text_parser.add_argument("--title", default="论文正文", help="Child page title to create or update.")
    text_parser.set_defaults(func=cmd_sync_text_page)

    tasks_parser = sub.add_parser("tasks", help="Poll and execute queued Notion agent tasks.")
    tasks_parser.add_argument("--once", action="store_true", help="Process the queue once and exit.")
    tasks_parser.add_argument("--interval", type=int, default=30, help="Polling interval in seconds.")
    tasks_parser.set_defaults(func=cmd_tasks)

    page_agent_parser = sub.add_parser("page-agent", help="Poll the existing Notion page communication database.")
    page_agent_parser.add_argument("--parent-page", required=True, help="Notion parent page id.")
    page_agent_parser.add_argument("--once", action="store_true", help="Process pending tasks once and exit.")
    page_agent_parser.add_argument("--interval", type=int, default=30, help="Polling interval in seconds.")
    page_agent_parser.add_argument("--write-local", action="store_true", help="Allow Claude Code to edit local paper files.")
    page_agent_parser.add_argument("--commit", action="store_true", help="Commit paper.tex changes after a write-local task.")
    page_agent_parser.add_argument("--sync-text", action="store_true", help="Refresh the Notion paper text page after committed edits.")
    page_agent_parser.set_defaults(func=cmd_page_agent)

    sync_changes_parser = sub.add_parser("sync-changes", help="Apply pending Modification Log entries to local LaTeX.")
    sync_changes_parser.add_argument("--parent-page", required=True, help="Notion parent page id.")
    sync_changes_parser.set_defaults(func=cmd_sync_changes)

    status_parser = sub.add_parser("status", help="Show local sync state.")
    status_parser.set_defaults(func=cmd_status)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
