"""Sync the paper body into a Notion child page as readable prose."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .latex_text import paper_text_blocks


def sync_text_page(
    api: Any,
    paper_dir: Path,
    parent_page_id: str,
    title: str = "论文正文",
    main_tex: str = "paper.tex",
) -> dict[str, Any]:
    paper_dir = paper_dir.resolve()
    paper_title, blocks = paper_text_blocks(paper_dir / main_tex)
    child_pages = api.discover_child_pages(parent_page_id)
    page_id = child_pages.get(title)
    if page_id:
        api.replace_page_content(page_id, blocks)
    else:
        page_id = api.create_child_page(parent_page_id, title, children=blocks)
    return {"title": title, "paper_title": paper_title, "page_id": page_id, "blocks": len(blocks)}
