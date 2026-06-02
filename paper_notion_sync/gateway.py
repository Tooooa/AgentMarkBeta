"""Poll Notion Agent Tasks and dispatch safe local paper actions."""

from __future__ import annotations

import json
import os
import shlex
import subprocess
from pathlib import Path
from typing import Any

from .notion_api import code_blocks, date_value, rich_text, select_value
from .state import save_state
from .sync import sync_paper
from .tasks import build_task_payload, resolve_task_action


def prop_title(page: dict[str, Any], name: str) -> str:
    values = page.get("properties", {}).get(name, {}).get("title", [])
    return "".join(item.get("plain_text", "") for item in values)


def prop_text(page: dict[str, Any], name: str) -> str:
    values = page.get("properties", {}).get(name, {}).get("rich_text", [])
    return "".join(item.get("plain_text", "") for item in values)


def prop_select(page: dict[str, Any], name: str) -> str:
    value = page.get("properties", {}).get(name, {}).get("select")
    return value.get("name", "") if value else ""


def queued_tasks(api: Any, tasks_db: str) -> list[dict[str, Any]]:
    pages = api.query_database(tasks_db, {"property": "Status", "select": {"equals": "Queued"}})
    return [
        {
            "id": page["id"],
            "title": prop_title(page, "Task"),
            "task_type": prop_select(page, "Task Type"),
            "instruction": prop_text(page, "Instruction"),
            "target_file": prop_text(page, "Target File"),
            "target_section": prop_text(page, "Target Section"),
        }
        for page in pages
    ]


def set_task_status(api: Any, task_id: str, status: str, result: str = "", error: str = "") -> None:
    props = {"Status": select_value(status)}
    if status == "Running":
        props["Started At"] = date_value()
    if status in {"Done", "Failed", "Needs Approval"}:
        props["Finished At"] = date_value()
    if result:
        props["Result"] = rich_text(result)
    if error:
        props["Error"] = rich_text(error)
    api.update_page(task_id, props)
    if result or error:
        blocks = code_blocks(result or error, language="markdown")
        api.replace_page_content(task_id, blocks)


def run_agent_command(task: dict[str, Any], paper_dir: Path, paper_page_id: str) -> str:
    command = os.environ.get("PAPER_AGENT_COMMAND", "")
    payload = build_task_payload(task, paper_dir, paper_page_id)
    payload_dir = paper_dir / ".paper_notion_sync" / "tasks"
    payload_dir.mkdir(parents=True, exist_ok=True)
    payload_path = payload_dir / f"{task['id'].replace('-', '')}.json"
    payload_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    if not command:
        return (
            "Queued local agent payload, but PAPER_AGENT_COMMAND is not set.\n"
            f"Payload: {payload_path}\n"
            "Set PAPER_AGENT_COMMAND to let the gateway invoke your local agent."
        )

    result = subprocess.run(
        shlex.split(command),
        cwd=str(paper_dir),
        input=json.dumps(payload, ensure_ascii=False),
        capture_output=True,
        text=True,
        check=False,
    )
    output = (result.stdout or "") + ("\n" + result.stderr if result.stderr else "")
    if result.returncode != 0:
        raise RuntimeError(output or f"Agent command failed with exit code {result.returncode}")
    return output.strip() or f"Agent command completed. Payload: {payload_path}"


def run_task(api: Any, paper_dir: Path, state: dict[str, Any], task: dict[str, Any], main_tex: str = "paper.tex") -> str:
    action = resolve_task_action(task)
    if action.kind == "local" and task["task_type"] == "compile_pdf":
        result = subprocess.run(action.argv, cwd=str(paper_dir), capture_output=True, text=True, check=False)
        output = (result.stdout or "") + ("\n" + result.stderr if result.stderr else "")
        if result.returncode != 0:
            raise RuntimeError(output)
        return output.strip() or "PDF compiled successfully."
    if action.kind == "local" and task["task_type"] == "sync_paper":
        summary = sync_paper(api, paper_dir, state, main_tex=main_tex)
        save_state(paper_dir, state)
        return json.dumps(summary, ensure_ascii=False)
    if action.kind == "agent":
        return run_agent_command(task, paper_dir, state.get("paper_page_id", ""))
    return f"Unsupported task type: {task.get('task_type', '')}"


def poll_once(api: Any, paper_dir: Path, state: dict[str, Any], main_tex: str = "paper.tex") -> int:
    tasks_db = state["databases"]["agent_tasks"]
    tasks = queued_tasks(api, tasks_db)
    for task in tasks:
        set_task_status(api, task["id"], "Running")
        try:
            result = run_task(api, paper_dir, state, task, main_tex=main_tex)
            final_status = "Needs Approval" if task["task_type"] in {"propose_patch", "polish_language"} else "Done"
            set_task_status(api, task["id"], final_status, result=result)
        except Exception as exc:
            set_task_status(api, task["id"], "Failed", error=str(exc))
    return len(tasks)
