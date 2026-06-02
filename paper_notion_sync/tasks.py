"""Local task dispatch for Notion-created paper agent tasks."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class TaskAction:
    kind: str
    argv: list[str]


LOCAL_TASKS: dict[str, TaskAction] = {
    "compile_pdf": TaskAction(kind="local", argv=["make"]),
    "sync_paper": TaskAction(kind="local", argv=[]),
}

AGENT_TASK_TYPES = {"review_section", "polish_language", "check_citations", "propose_patch"}


def resolve_task_action(task: dict[str, Any]) -> TaskAction:
    """Map a Notion task type to a local action without trusting instructions as shell."""
    task_type = task.get("task_type", "")
    if task_type in LOCAL_TASKS:
        return LOCAL_TASKS[task_type]
    if task_type in AGENT_TASK_TYPES:
        return TaskAction(kind="agent", argv=[])
    return TaskAction(kind="unsupported", argv=[])


def build_task_payload(
    task: dict[str, Any],
    paper_dir: Path,
    paper_page_id: str,
) -> dict[str, Any]:
    """Build the JSON payload given to an optional local agent command."""
    return {
        "paper": {
            "directory": str(paper_dir),
            "page_id": paper_page_id,
        },
        "task": {
            "id": task.get("id", ""),
            "task_type": task.get("task_type", ""),
            "instruction": task.get("instruction", ""),
            "target_file": task.get("target_file", ""),
            "target_section": task.get("target_section", ""),
        },
    }
