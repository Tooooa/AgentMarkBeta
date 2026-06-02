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


@dataclass(frozen=True)
class ChangeLogEntry:
    page_id: str
    summary: str
    location: str
    reason: str
    status: str


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


def build_claude_prompt(task: CommunicationTask, paper_dir: Path, allow_write: bool = False) -> str:
    paper_tex = paper_dir / "paper.tex"
    write_rule = (
        f"本次允许运行本地写回：如果任务明确要求写回本地 LaTeX，可以修改 {paper_tex.name}。"
        if allow_write
        else "本次只允许审阅和回复：不要修改任何本地文件；如果需要改论文，请把建议写清楚，让 Notion AI/用户登记到「修改日志」后再由写回流程处理。"
    )
    return f"""你是本地论文协作 agent，运行模型为 mimo-v2.5-pro。

你正在协作的论文仓库是：
{paper_dir}

主 LaTeX 文件是：
{paper_tex}

Notion 沟通区任务：
{task.title}

执行规则：
1. 先理解任务，再决定是否需要修改本地文件。
2. {write_rule}
3. 如果任务只是审阅、解释、给建议，请只给出清晰回复。
4. 只允许改论文正文相关内容，默认不要改实验数据、代码、图片和无关文件。
5. 修改后在最终回复里说明：是否修改了 paper.tex、修改位置、修改理由。
6. 回复使用中文，简洁但足够让 Notion AI/用户继续协作。
"""


def change_entry_to_task(entry: ChangeLogEntry) -> CommunicationTask:
    title = (
        "请根据 Notion 修改日志写回本地 LaTeX。\n"
        f"章节 / 位置：{entry.location or '未指定'}\n"
        f"改动摘要：{entry.summary}\n"
        f"理由：{entry.reason or '未填写'}"
    )
    return CommunicationTask(
        page_id=entry.page_id,
        title=title,
        status=entry.status,
        proposer="修改日志",
        agent_reply="",
    )


def run_claude_code(task: CommunicationTask, paper_dir: Path, timeout: int = 600, allow_write: bool = False) -> str:
    prompt = build_claude_prompt(task, paper_dir, allow_write=allow_write)
    allowed_tools = "Read,Glob,Grep"
    if allow_write:
        allowed_tools = "Read,Edit,MultiEdit,Glob,Grep"
    cmd = [
        "claude",
        "--print",
        "--model",
        "mimo-v2.5-pro",
        "--permission-mode",
        "acceptEdits",
        "--allowedTools",
        allowed_tools,
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


def pending_changelog_entries(api: Any, changelog_db_id: str) -> list[ChangeLogEntry]:
    pages = api.query_database(
        changelog_db_id,
        {"property": "同步状态", "status": {"equals": "待同步"}},
    )
    entries: list[ChangeLogEntry] = []
    for page in pages:
        entries.append(
            ChangeLogEntry(
                page_id=page["id"],
                summary=_title_prop(page, "改动摘要"),
                location=_rich_text_prop(page, "章节 / 位置"),
                reason=_rich_text_prop(page, "理由"),
                status=_status_prop(page, "同步状态"),
            )
        )
    return entries


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


def mark_changelog_synced(api: Any, entry: ChangeLogEntry, reply: str) -> None:
    reason = entry.reason
    suffix = f"\n\n本地 agent 同步结果：\n{reply[:1200]}"
    api.update_page(
        entry.page_id,
        {
            "同步状态": status_value("已同步"),
            "理由": rich_text((reason + suffix).strip()),
        },
    )


def poll_page_once(
    api: Any,
    paper_dir: Path,
    parent_page_id: str,
    runner: Callable[[CommunicationTask, Path], str] | None = None,
    allow_write: bool = False,
    commit_changes: bool = False,
    sync_text: bool = False,
) -> int:
    databases = discover_page_databases(api, parent_page_id)
    chat_db_id = databases[CHAT_DB_TITLE]
    changelog_db_id = databases.get(CHANGELOG_DB_TITLE, "")
    tasks = pending_tasks(api, chat_db_id)

    processed = 0
    for task in tasks:
        set_task_status(api, task, RUNNING_STATUS)
        try:
            if runner is None:
                reply = run_claude_code(task, paper_dir, allow_write=allow_write)
            else:
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


def sync_changelog_once(
    api: Any,
    paper_dir: Path,
    parent_page_id: str,
    runner: Callable[[CommunicationTask, Path], str] | None = None,
) -> int:
    databases = discover_page_databases(api, parent_page_id)
    changelog_db_id = databases[CHANGELOG_DB_TITLE]
    entries = pending_changelog_entries(api, changelog_db_id)

    processed = 0
    for entry in entries:
        task = change_entry_to_task(entry)
        try:
            if runner is None:
                reply = run_claude_code(task, paper_dir, allow_write=True)
            else:
                reply = runner(task, paper_dir)
            committed = git_commit_paper(paper_dir, task)
            if committed:
                sync_text_page(api, paper_dir, parent_page_id, title=TEXT_PAGE_TITLE)
            mark_changelog_synced(api, entry, reply or "已处理。")
        except Exception as exc:
            mark_changelog_synced(api, entry, f"同步失败：{exc}")
        processed += 1
    return processed
