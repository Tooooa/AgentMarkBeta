"""Local paper to Notion synchronization."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from .latex import extract_sections, extract_title
from .notion_api import (
    code_blocks,
    date_value,
    heading_block,
    paragraph_block,
    relation_value,
    rich_text,
    select_value,
    title_text,
    url_value,
)


def current_commit(repo_dir: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=str(repo_dir),
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def upsert_page(api: Any, database_id: str, title_property: str, title: str, properties: dict[str, Any], children=None) -> str:
    existing = api.find_page_by_title(database_id, title_property, title)
    if existing:
        api.update_page(existing["id"], properties)
        if children is not None:
            api.replace_page_content(existing["id"], children)
        return existing["id"]
    return api.create_page(database_id, properties, children=children)


def upsert_paper_page(
    api: Any,
    state: dict[str, Any],
    database_id: str,
    title: str,
    properties: dict[str, Any],
    children=None,
) -> str:
    page_id = state.get("paper_page_id", "")
    if page_id:
        api.update_page(page_id, properties)
        if children is not None:
            api.replace_page_content(page_id, children)
        return page_id
    return upsert_page(api, database_id, "Title", title, properties, children=children)


def paper_properties(paper_dir: Path, title: str, main_tex: str, commit: str, pdf_path: Path) -> dict[str, Any]:
    return {
        "Title": title_text(title),
        "Status": select_value("Draft"),
        "Repo Path": rich_text(str(paper_dir)),
        "Main Tex File": rich_text(main_tex),
        "Current Commit": rich_text(commit),
        "Latest PDF": url_value(""),
        "Last Synced": date_value(),
        "Notes": rich_text(f"Local PDF: {pdf_path}" if pdf_path.exists() else "Local PDF not found"),
    }


def section_properties(section, paper_page_id: str) -> dict[str, Any]:
    level_name = {1: "section", 2: "subsection", 3: "subsubsection"}[section.level]
    return {
        "Name": title_text(section.title),
        "Paper": relation_value(paper_page_id),
        "Level": select_value(level_name),
        "Source File": rich_text(section.source_file),
        "Label": rich_text(section.label),
        "Content Hash": rich_text(section.content_hash),
        "Summary": rich_text(section.summary),
        "Last Synced": date_value(),
    }


def section_blocks(section) -> list[dict[str, Any]]:
    blocks = [heading_block(section.title, section.level), paragraph_block(f"Label: {section.label or '(none)'}")]
    blocks.extend(code_blocks(section.content, language="latex"))
    return blocks


def create_sync_run(
    api: Any,
    state: dict[str, Any],
    paper_dir: Path,
    paper_page_id: str,
    title: str,
    status: str,
    logs: str,
) -> str | None:
    db_id = state.get("databases", {}).get("sync_runs")
    if not db_id:
        return None
    commit = current_commit(paper_dir)
    return api.create_page(
        db_id,
        {
            "Run": title_text(title),
            "Paper": relation_value(paper_page_id),
            "Direction": select_value("Local to Notion"),
            "Status": select_value(status),
            "Commit Before": rich_text(commit),
            "Commit After": rich_text(commit),
            "Started At": date_value(),
            "Finished At": date_value(),
            "Logs": rich_text(logs),
        },
    )


def sync_paper(api: Any, paper_dir: Path, state: dict[str, Any], main_tex: str = "paper.tex") -> dict[str, Any]:
    paper_dir = paper_dir.resolve()
    tex_path = paper_dir / main_tex
    title = extract_title(tex_path)
    commit = current_commit(paper_dir)
    paper_db = state["databases"]["papers"]
    sections_db = state["databases"]["paper_sections"]

    paper_page_id = upsert_paper_page(
        api,
        state,
        paper_db,
        title,
        paper_properties(paper_dir, title, main_tex, commit, paper_dir / "paper.pdf"),
        children=[heading_block(title, 1), paragraph_block(f"Synced from {paper_dir}")],
    )
    state["paper_page_id"] = paper_page_id

    sections = extract_sections(tex_path)
    for section in sections:
        upsert_page(
            api,
            sections_db,
            "Name",
            section.title,
            section_properties(section, paper_page_id),
            children=section_blocks(section),
        )

    if state.get("databases", {}).get("sync_runs"):
        create_sync_run(
            api,
            state,
            paper_dir,
            paper_page_id,
            f"Sync {title}",
            "Done",
            f"Synced {len(sections)} sections from {main_tex}.",
        )

    return {"paper_title": title, "paper_page_id": paper_page_id, "sections": len(sections)}
