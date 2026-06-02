from pathlib import Path

from paper_notion_sync.latex import extract_sections
from paper_notion_sync.schemas import build_database_plan
from paper_notion_sync.sync import sync_paper
from paper_notion_sync.tasks import build_task_payload, resolve_task_action


class FakeNotion:
    def __init__(self) -> None:
        self.pages = []
        self.replaced = []

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
        page = next(page for page in self.pages if page["id"] == page_id)
        page["properties"].update(properties)

    def replace_page_content(self, page_id, blocks):
        self.replaced.append((page_id, blocks))


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


def test_database_plan_creates_papers_first_and_relates_dependents() -> None:
    plan = build_database_plan()

    assert [item.key for item in plan][:2] == ["papers", "paper_sections"]
    assert plan[0].title == "Papers"
    assert "Status" in plan[0].properties
    assert plan[1].relation_to == "papers"
    assert "Task Type" in next(item.properties for item in plan if item.key == "agent_tasks")


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
