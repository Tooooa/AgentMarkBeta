from pathlib import Path

from paper_notion_sync.latex import extract_sections
from paper_notion_sync.latex import extract_title
from paper_notion_sync.latex_text import latex_to_plain_notion_blocks
from paper_notion_sync.notion_api import NotionAPI
from paper_notion_sync.page_agent import CommunicationTask
from paper_notion_sync.page_agent import build_claude_prompt
from paper_notion_sync.page_agent import read_long_memory
from paper_notion_sync.page_agent import poll_page_once
from paper_notion_sync.page_agent import split_agent_reply
from paper_notion_sync.page_agent import sync_changelog_once
from paper_notion_sync.schemas import build_database_plan
from paper_notion_sync.schemas import materialize_properties
from paper_notion_sync.sync import sync_paper
from paper_notion_sync.text_page import sync_text_page
from paper_notion_sync.tasks import build_task_payload, resolve_task_action


class FakeNotion:
    def __init__(self) -> None:
        self.pages = []
        self.replaced = []
        self.child_pages = {}
        self.updated = []
        self.queries = []

    def find_page_by_title(self, database_id, title_property, title):
        for page in self.pages:
            if page["database_id"] == database_id and page["title"] == title:
                return page
        return None

    def create_page(self, database_id, properties, children=None):
        title = {}
        for key in ("Title", "Name", "Run", "Task", "Suggestion", "Artifact"):
            if key in properties:
                title = properties[key]
                break
        title_text = title["title"][0]["text"]["content"]
        page = {
            "id": f"page-{len(self.pages) + 1}",
            "database_id": database_id,
            "title": title_text,
            "properties": properties,
            "children": children or [],
        }
        self.pages.append(page)
        return page["id"]

    def update_page(self, page_id, properties):
        self.updated.append((page_id, properties))
        for page in self.pages:
            if page["id"] == page_id:
                page["properties"].update(properties)
                break

    def replace_page_content(self, page_id, blocks):
        self.replaced.append((page_id, blocks))

    def list_block_children(self, page_id):
        page = next(page for page in self.pages if page["id"] == page_id)
        return page.get("children", [])

    def discover_child_pages(self, parent_page_id):
        return dict(self.child_pages)

    def discover_child_databases(self, parent_page_id):
        return {"沟通区": "db-chat", "修改日志": "db-log"}

    def create_child_page(self, parent_page_id, title, children=None):
        page_id = f"child-{len(self.child_pages) + 1}"
        self.child_pages[title] = page_id
        self.replaced.append((page_id, children or []))
        return page_id

    def query_database(self, database_id, filter_obj=None):
        self.queries.append((database_id, filter_obj))
        return [page for page in self.pages if page["database_id"] == database_id]


class FakeBlockNotion(NotionAPI):
    def __init__(self) -> None:
        self.deleted = []
        self.appended = []

    def list_block_children(self, block_id):
        return [
            {"id": "active-block"},
            {"id": "archived-block", "archived": True},
            {"id": "trashed-block", "in_trash": True},
        ]

    def request(self, method, path, payload=None):
        if method == "DELETE":
            self.deleted.append(path)
            return {}

    def append_blocks(self, block_id, blocks):
        self.appended.append((block_id, blocks))


def test_extract_sections_includes_labels_and_stable_hashes(tmp_path: Path) -> None:
    tex = tmp_path / "paper.tex"
    tex.write_text(
        r"""
\section{Introduction}
\label{sec:intro}
Intro text.

\subsection{Motivation}
More text.

\section{Design}
\label{sec:design}
Design text.
""".strip(),
        encoding="utf-8",
    )

    sections = extract_sections(tex)

    assert [section.title for section in sections] == [
        "Introduction",
        "Motivation",
        "Design",
    ]
    assert sections[0].level == 1
    assert sections[1].level == 2
    assert sections[0].label == "sec:intro"
    assert sections[2].label == "sec:design"
    assert len(sections[0].content_hash) == 16
    assert sections[0].content_hash == extract_sections(tex)[0].content_hash


def test_extract_title_expands_simple_newcommand_macros(tmp_path: Path) -> None:
    tex = tmp_path / "paper.tex"
    tex.write_text(
        r"\newcommand{\framework}{AsymMark}" "\n" r"\title{\framework: Weakly Asymmetric Behavioral Watermarking}",
        encoding="utf-8",
    )

    assert extract_title(tex) == "AsymMark: Weakly Asymmetric Behavioral Watermarking"


def test_latex_to_plain_notion_blocks_uses_headings_and_keeps_tables_as_latex() -> None:
    blocks = latex_to_plain_notion_blocks(
        r"""
\begin{abstract}
This is \framework{} in prose.
\end{abstract}
\section{Introduction}
Plain text with \textbf{bold words}.
\subsection{Results}
\begin{table}
\begin{tabular}{lr}
A & 1 \\
\end{tabular}
\end{table}
More prose.
""",
        macros={"framework": "AsymMark"},
    )

    assert [block["type"] for block in blocks] == [
        "heading_1",
        "paragraph",
        "heading_1",
        "paragraph",
        "heading_2",
        "code",
        "paragraph",
    ]
    assert blocks[0]["heading_1"]["rich_text"][0]["text"]["content"] == "Abstract"
    assert blocks[1]["paragraph"]["rich_text"][0]["text"]["content"] == "This is AsymMark in prose."
    assert blocks[5]["code"]["language"] == "latex"
    assert "\\begin{tabular}" in blocks[5]["code"]["rich_text"][0]["text"]["content"]


def test_database_plan_creates_papers_first_and_relates_dependents() -> None:
    plan = build_database_plan()

    assert [item.key for item in plan][:2] == ["papers", "paper_sections"]
    assert plan[0].title == "Papers"
    assert "Status" in plan[0].properties
    assert plan[1].relation_to == "papers"
    assert "Task Type" in next(item.properties for item in plan if item.key == "agent_tasks")


def test_materialized_relation_uses_notion_dual_property_shape() -> None:
    spec = build_database_plan()[1]
    props = materialize_properties(spec, {"papers": "papers-db-id"})

    assert props["Paper"] == {
        "relation": {
            "database_id": "papers-db-id",
            "type": "dual_property",
            "dual_property": {},
        }
    }


def test_replace_page_content_skips_archived_blocks() -> None:
    api = FakeBlockNotion()

    api.replace_page_content("page-id", [{"type": "paragraph", "paragraph": {"rich_text": []}}])

    assert api.deleted == ["/blocks/active-block"]
    assert api.appended[0][0] == "page-id"


def test_task_resolution_uses_local_whitelist_not_notion_commands() -> None:
    task = {
        "id": "task-page-id",
        "task_type": "compile_pdf",
        "instruction": "please run rm -rf /",
        "target_file": "paper.tex",
        "target_section": "",
    }

    action = resolve_task_action(task)
    payload = build_task_payload(
        task,
        paper_dir=Path("/repo/papers/example"),
        paper_page_id="paper-page-id",
    )

    assert action.kind == "local"
    assert action.argv == ["make"]
    assert payload["task"]["instruction"] == "please run rm -rf /"
    assert payload["paper"]["directory"] == "/repo/papers/example"


def test_sync_paper_upserts_paper_and_sections(tmp_path: Path) -> None:
    (tmp_path / "paper.tex").write_text(
        r"\title{Demo Paper}" "\n" r"\section{Intro}" "\n" "Hello.",
        encoding="utf-8",
    )
    api = FakeNotion()
    state = {
        "databases": {
            "papers": "db-papers",
            "paper_sections": "db-sections",
            "sync_runs": "db-runs",
            "artifacts": "db-artifacts",
        },
        "paper_page_id": "",
    }

    summary = sync_paper(api, tmp_path, state, main_tex="paper.tex")

    assert summary["paper_title"] == "Demo Paper"
    assert summary["sections"] == 1
    assert state["paper_page_id"] == "page-1"
    assert [page["database_id"] for page in api.pages][:2] == ["db-papers", "db-sections"]


def test_sync_paper_skips_unchanged_section_content(tmp_path: Path) -> None:
    (tmp_path / "paper.tex").write_text(
        r"\title{Demo Paper}" "\n" r"\section{Intro}" "\n" "Hello.",
        encoding="utf-8",
    )
    api = FakeNotion()
    state = {
        "databases": {
            "papers": "db-papers",
            "paper_sections": "db-sections",
        },
        "paper_page_id": "",
    }

    sync_paper(api, tmp_path, state, main_tex="paper.tex")
    api.replaced.clear()
    sync_paper(api, tmp_path, state, main_tex="paper.tex")

    replaced_titles = [
        next(page["title"] for page in api.pages if page["id"] == page_id)
        for page_id, _ in api.replaced
    ]
    assert replaced_titles == ["Demo Paper"]


def test_sync_text_page_reuses_existing_child_page(tmp_path: Path) -> None:
    (tmp_path / "paper.tex").write_text(
        r"\title{Demo Paper}" "\n" r"\section{Intro}" "\n" "Hello.",
        encoding="utf-8",
    )
    api = FakeNotion()
    api.child_pages["论文正文"] = "existing-child-page"

    summary = sync_text_page(api, tmp_path, parent_page_id="parent-id", title="论文正文")

    assert summary["page_id"] == "existing-child-page"
    assert summary["blocks"] == 3
    assert api.replaced[-1][0] == "existing-child-page"
    assert api.replaced[-1][1][1]["heading_1"]["rich_text"][0]["text"]["content"] == "Intro"


def test_build_claude_prompt_defaults_to_read_only_contract(tmp_path: Path) -> None:
    task = CommunicationTask(
        page_id="task-page",
        title="请把 introduction 第二段写回 LaTeX",
        status="待回答",
        proposer="AI",
        agent_reply="",
    )

    prompt = build_claude_prompt(task, tmp_path)

    assert "mimo-v2.5-pro" in prompt
    assert "/Users/local/AgentMarkBeta" in prompt
    assert "/Users/local/AgentMarkBeta/实验数据/remote_data/output-0510" in prompt
    assert "paper.tex" in prompt
    assert "不要修改任何本地文件" in prompt
    assert "修改日志" in prompt
    assert "LONG_MEMORY" in prompt
    assert task.title in prompt


def test_build_claude_prompt_can_allow_latex_writeback(tmp_path: Path) -> None:
    task = CommunicationTask(
        page_id="task-page",
        title="请把 introduction 第二段写回 LaTeX",
        status="待回答",
        proposer="AI",
        agent_reply="",
    )

    prompt = build_claude_prompt(task, tmp_path, allow_write=True)

    assert "允许运行本地写回" in prompt
    assert "可以修改 paper.tex" in prompt


def test_split_agent_reply_extracts_optional_long_memory() -> None:
    parsed = split_agent_reply("回复正文。\nLONG_MEMORY: 以后优先检查 Introduction 贡献表述。")

    assert parsed.reply == "回复正文。"
    assert parsed.memory == "以后优先检查 Introduction 贡献表述。"


def test_poll_page_once_updates_reply_and_status(tmp_path: Path) -> None:
    (tmp_path / "paper.tex").write_text(r"\title{Demo}" "\n" r"\section{Intro}" "\n" "Hello.", encoding="utf-8")
    api = FakeNotion()
    api.child_pages["论文正文"] = "child-paper"
    api.pages.append(
        {
            "id": "task-page",
            "database_id": "db-chat",
            "title": "请评价 introduction",
            "properties": {
                "问题 / 意见": {"title": [{"plain_text": "请评价 introduction"}]},
                "状态": {"status": {"name": "待回答"}},
                "提出者": {"select": {"name": "AI"}},
                "agent 回复": {"rich_text": []},
            },
            "children": [],
        }
    )

    processed = poll_page_once(
        api,
        tmp_path,
        parent_page_id="parent-id",
        runner=lambda task, paper_dir: "这段需要更明确地说明贡献。\nLONG_MEMORY: Introduction 容易需要强化贡献。",
        commit_changes=False,
    )

    assert processed == 1
    status_values = [
        props["状态"]["status"]["name"]
        for _, props in api.updated
        if "状态" in props
    ]
    assert status_values == ["讨论中", "已回答"]
    final_props = api.updated[-1][1]
    assert final_props["agent 回复"]["rich_text"][0]["text"]["content"] == "这段需要更明确地说明贡献。"
    assert "Introduction 容易需要强化贡献" in read_long_memory(tmp_path)


def test_sync_changelog_once_marks_pending_log_as_synced(tmp_path: Path) -> None:
    (tmp_path / "paper.tex").write_text(r"\title{Demo}" "\n" r"\section{Intro}" "\n" "Hello.", encoding="utf-8")
    api = FakeNotion()
    api.child_pages["论文正文"] = "child-paper"
    api.pages.append(
        {
            "id": "log-page",
            "database_id": "db-log",
            "title": "强化 introduction 的贡献表述",
            "properties": {
                "改动摘要": {"title": [{"plain_text": "强化 introduction 的贡献表述"}]},
                "章节 / 位置": {"rich_text": [{"plain_text": "Introduction"}]},
                "理由": {"rich_text": [{"plain_text": "贡献不够集中"}]},
                "同步状态": {"status": {"name": "待同步"}},
            },
            "children": [],
        }
    )

    processed = sync_changelog_once(
        api,
        tmp_path,
        parent_page_id="parent-id",
        runner=lambda task, paper_dir: "已根据修改日志处理。",
    )

    assert processed == 1
    final_props = api.updated[-1][1]
    assert final_props["同步状态"]["status"]["name"] == "已同步"
    assert "已根据修改日志处理" in final_props["理由"]["rich_text"][0]["text"]["content"]
