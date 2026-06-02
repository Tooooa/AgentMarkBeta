"""State file handling for paper Notion sync."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


STATE_DIRNAME = ".paper_notion_sync"
STATE_FILENAME = "state.json"


def state_path(paper_dir: Path) -> Path:
    return paper_dir / STATE_DIRNAME / STATE_FILENAME


def load_state(paper_dir: Path) -> dict[str, Any]:
    path = state_path(paper_dir)
    if not path.exists():
        return {"databases": {}, "paper_page_id": ""}
    return json.loads(path.read_text(encoding="utf-8"))


def save_state(paper_dir: Path, state: dict[str, Any]) -> None:
    path = state_path(paper_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
