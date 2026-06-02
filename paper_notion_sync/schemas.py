"""Notion database schemas for the paper iteration control plane."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DatabaseSpec:
    key: str
    title: str
    properties: dict[str, Any]
    relation_to: str | None = None


def title_prop() -> dict[str, Any]:
    return {"title": {}}


def rich_text_prop() -> dict[str, Any]:
    return {"rich_text": {}}


def date_prop() -> dict[str, Any]:
    return {"date": {}}


def url_prop() -> dict[str, Any]:
    return {"url": {}}


def number_prop() -> dict[str, Any]:
    return {"number": {}}


def select_prop(options: list[str]) -> dict[str, Any]:
    return {"select": {"options": [{"name": name} for name in options]}}


def relation_prop(database_id: str) -> dict[str, Any]:
    return {
        "relation": {
            "database_id": database_id,
            "type": "dual_property",
            "dual_property": {},
        }
    }


def build_database_plan() -> list[DatabaseSpec]:
    """Return database creation order. Papers comes first for relations."""
    return [
        DatabaseSpec(
            key="papers",
            title="Papers",
            properties={
                "Title": title_prop(),
                "Status": select_prop(["Draft", "Reviewing", "Revising", "Submitted"]),
                "Repo Path": rich_text_prop(),
                "Main Tex File": rich_text_prop(),
                "Current Commit": rich_text_prop(),
                "Latest PDF": url_prop(),
                "Last Synced": date_prop(),
                "Notes": rich_text_prop(),
            },
        ),
        DatabaseSpec(
            key="paper_sections",
            title="Paper Sections",
            relation_to="papers",
            properties={
                "Name": title_prop(),
                "Paper": rich_text_prop(),
                "Level": select_prop(["section", "subsection", "subsubsection"]),
                "Source File": rich_text_prop(),
                "Label": rich_text_prop(),
                "Content Hash": rich_text_prop(),
                "Summary": rich_text_prop(),
                "Last Synced": date_prop(),
            },
        ),
        DatabaseSpec(
            key="agent_tasks",
            title="Agent Tasks",
            relation_to="papers",
            properties={
                "Task": title_prop(),
                "Paper": rich_text_prop(),
                "Task Type": select_prop(
                    ["sync_paper", "compile_pdf", "review_section", "polish_language", "check_citations", "propose_patch"]
                ),
                "Status": select_prop(["Queued", "Running", "Needs Approval", "Done", "Failed"]),
                "Priority": select_prop(["Low", "Normal", "High"]),
                "Instruction": rich_text_prop(),
                "Target File": rich_text_prop(),
                "Target Section": rich_text_prop(),
                "Started At": date_prop(),
                "Finished At": date_prop(),
                "Result": rich_text_prop(),
                "Error": rich_text_prop(),
            },
        ),
        DatabaseSpec(
            key="review_suggestions",
            title="Review Suggestions",
            relation_to="papers",
            properties={
                "Suggestion": title_prop(),
                "Paper": rich_text_prop(),
                "Section": rich_text_prop(),
                "Severity": select_prop(["Low", "Medium", "High"]),
                "Category": select_prop(["Logic", "Language", "Citation", "Experiment", "Structure"]),
                "Status": select_prop(["Open", "Accepted", "Rejected", "Applied"]),
                "Evidence": rich_text_prop(),
                "Proposed Change": rich_text_prop(),
                "Task Page ID": rich_text_prop(),
            },
        ),
        DatabaseSpec(
            key="sync_runs",
            title="Sync Runs",
            relation_to="papers",
            properties={
                "Run": title_prop(),
                "Paper": rich_text_prop(),
                "Direction": select_prop(["Local to Notion", "Notion to Local", "Agent Task"]),
                "Status": select_prop(["Running", "Done", "Failed"]),
                "Commit Before": rich_text_prop(),
                "Commit After": rich_text_prop(),
                "Started At": date_prop(),
                "Finished At": date_prop(),
                "Logs": rich_text_prop(),
            },
        ),
        DatabaseSpec(
            key="artifacts",
            title="Artifacts",
            relation_to="papers",
            properties={
                "Artifact": title_prop(),
                "Paper": rich_text_prop(),
                "Type": select_prop(["PDF", "Diff", "Compile Log", "Task Payload", "Other"]),
                "Local Path": rich_text_prop(),
                "URL": url_prop(),
                "Task Page ID": rich_text_prop(),
                "Created At": date_prop(),
            },
        ),
    ]


def materialize_properties(spec: DatabaseSpec, database_ids: dict[str, str]) -> dict[str, Any]:
    """Replace placeholder Paper relation with a real Notion relation."""
    properties = dict(spec.properties)
    if spec.relation_to:
        properties["Paper"] = relation_prop(database_ids[spec.relation_to])
    return properties
