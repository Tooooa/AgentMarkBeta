"""Bridge the existing Notion paper page to a local Claude Code agent."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .notion_api import date_value, rich_text, status_value, title_text
from .text_page import sync_text_page


CHAT_DB_TITLE = "沟通区"
CHANGELOG_DB_TITLE = "修改日志"
TEXT_PAGE_TITLE = "论文正文"
PENDING_STATUS = "待回答"
RUNNING_STATUS = "讨论中"
DONE_STATUS = "已回答"
FAILED_STATUS = "已回答"


@dataclass(frozen=True)
class CommunicationTask:
    page_id: str
    title: str
    status: str
    proposer: str
    agent_reply: str


def _title_prop(page: dict[str, Any], name: str) -> str:
    values = page.get("properties", {}).get(name, {}).get("title", [])
    return "".join(item.get("plain_text", item.get("text", {}).get("content", "")) for item in values)


def _rich_text_prop(page: dict[str, Any], name: str) -> str:
    values = page.get("properties", {}).get(name, {}).get("rich_text", [])
    return "".join(item.get("plain_text", item.get("text", {}).get("content", "")) for item in values)


def _status_prop(page: dict[str, Any], name: str) -> str:
    value = page.get("properties", {}).get(name, {}).get("status")
    return value.get("name", "") if value else ""


def _select_prop(page: dict[str, Any], name: str) -> str:
    value = page.get("properties", {}).get(name, {}).get("select")
    return value.get("name", "") if value else ""


def build_claude_prompt(task: CommunicationTask, paper_dir: Path) -> str:
    paper_tex = paper_dir / "paper.tex"
    return f"""你是本地论文协作 agent，运行模型为 mimo-v2.5-pro。

你正在协作的论文仓库是：
{paper_dir}

主 LaTeX 文件是：
{paper_tex}

Notion 沟通区任务：
{task.title}

执行规则：
1. 先理解任务，再决定是否需要修改本地文件。
2. 如果任务只是审阅、解释、给建议，请只给出清晰回复，不要修改文件。
3. 如果任务要求写回本地 LaTeX、同步 Notion 正文改动、应用修改、改 paper.tex，才可以修改 {paper_tex.name}。
4. 只允许改论文正文相关内容，默认不要改实验数据、代码、图片和无关文件。
5. 修改后在最终回复里说明：是否修改了 paper.tex、修改位置、修改理由。
6. 回复使用中文，简洁但足够让 Notion AI/用户继续协作。
"""


def run_claude_code(task: CommunicationTask, paper_dir: Path, timeout: int = 600) -> str:
    prompt = build_claude_prompt(task, paper_dir)
    cmd = [
        "claude",
        "--print",
        "--model",
        "mimo-v2.5-pro",
        "--permission-mode",
        "acceptEdits",
        "--allowedTools",
        "Read,Edit,MultiEdit,Glob,Grep",
        "--output-format",
        "json",
        prompt,
    ]
    result = subprocess.run(
        cmd,
        cwd=str(paper_dir),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or f"claude exited {result.returncode}")[:4000])
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return result.stdout.strip()
    if payload.get("is_error"):
        raise RuntimeError(payload.get("result") or "Claude Code returned an error")
    return str(payload.get("result", "")).strip()


def discover_page_databases(api: Any, parent_page_id: str) -> dict[str, str]:
    return api.discover_child_databases(parent_page_id)


def pending_tasks(api: Any, chat_db_id: str) -> list[CommunicationTask]:
    pages = api.query_database(
        chat_db_id,
        {"property": "状态", "status": {"equals": PENDING_STATUS}},
    )
    tasks: list[CommunicationTask] = []
    for page in pages:
        tasks.append(
            CommunicationTask(
                page_id=page["id"],
                title=_title_prop(page, "问题 / 意见"),
                status=_status_prop(page, "状态"),
                proposer=_select_prop(page, "提出者"),
                agent_reply=_rich_text_prop(page, "agent 回复"),
            )
        )
    return tasks


def set_task_status(api: Any, task: CommunicationTask, status: str, reply: str = "") -> None:
    props: dict[str, Any] = {"状态": status_value(status)}
    if reply:
        props["agent 回复"] = rich_text(reply)
    api.update_page(task.page_id, props)


def git_changed_paper(paper_dir: Path) -> bool:
    result = subprocess.run(
        ["git", "diff", "--quiet", "--", "paper.tex"],
        cwd=str(paper_dir),
        check=False,
    )
    return result.returncode == 1


def git_commit_paper(paper_dir: Path, task: CommunicationTask) -> bool:
    if not git_changed_paper(paper_dir):
        return False
    subprocess.run(["git", "add", "paper.tex"], cwd=str(paper_dir), check=True)
    subprocess.run(
        ["git", "commit", "-m", f"Apply Notion paper task: {task.title[:48]}"],
        cwd=str(paper_dir),
        check=True,
    )
    return True


def create_changelog(api: Any, changelog_db_id: str, task: CommunicationTask, reply: str, committed: bool) -> None:
    summary = task.title[:120] or "Notion agent task"
    api.create_page(
        changelog_db_id,
        {
            "改动摘要": title_text(summary),
            "章节 / 位置": rich_text("paper.tex"),
            "理由": rich_text(reply[:1800]),
            "同步状态": status_value("已同步" if committed else "待同步"),
        },
        children=None,
    )


def poll_page_once(
    api: Any,
    paper_dir: Path,
    parent_page_id: str,
    runner: Callable[[CommunicationTask, Path], str] = run_claude_code,
    commit_changes: bool = True,
    sync_text: bool = True,
) -> int:
    databases = discover_page_databases(api, parent_page_id)
    chat_db_id = databases[CHAT_DB_TITLE]
    changelog_db_id = databases.get(CHANGELOG_DB_TITLE, "")
    tasks = pending_tasks(api, chat_db_id)

    processed = 0
    for task in tasks:
        set_task_status(api, task, RUNNING_STATUS)
        try:
            reply = runner(task, paper_dir)
            committed = git_commit_paper(paper_dir, task) if commit_changes else False
            if committed and sync_text:
                sync_text_page(api, paper_dir, parent_page_id, title=TEXT_PAGE_TITLE)
            if changelog_db_id and (committed or "修改" in reply or "paper.tex" in reply):
                create_changelog(api, changelog_db_id, task, reply, committed)
            set_task_status(api, task, DONE_STATUS, reply=reply or "已处理。")
        except Exception as exc:
            set_task_status(api, task, FAILED_STATUS, reply=f"本地 agent 执行失败：{exc}")
        processed += 1
    return processed
