"""Small Notion REST client used by the paper sync bridge."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any


NOTION_VERSION = "2022-06-28"
BASE_URL = "https://api.notion.com/v1"
MAX_BLOCKS_PER_REQUEST = 100


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def rich_text(value: str, limit: int = 1900) -> dict[str, Any]:
    return {"rich_text": [{"type": "text", "text": {"content": value[:limit]}}]} if value else {"rich_text": []}


def title_text(value: str) -> dict[str, Any]:
    return {"title": [{"type": "text", "text": {"content": value[:1900]}}]}


def select_value(value: str) -> dict[str, Any]:
    return {"select": {"name": value}} if value else {"select": None}


def date_value(value: str | None = None) -> dict[str, Any]:
    return {"date": {"start": value or now_iso()}}


def url_value(value: str) -> dict[str, Any]:
    return {"url": value or None}


def relation_value(page_id: str) -> dict[str, Any]:
    return {"relation": [{"id": page_id}]} if page_id else {"relation": []}


def paragraph_block(text: str) -> dict[str, Any]:
    return {
        "object": "block",
        "type": "paragraph",
        "paragraph": {"rich_text": [{"type": "text", "text": {"content": text[:1900]}}]},
    }


def heading_block(text: str, level: int = 2) -> dict[str, Any]:
    level = min(max(level, 1), 3)
    return {
        "object": "block",
        "type": f"heading_{level}",
        f"heading_{level}": {"rich_text": [{"type": "text", "text": {"content": text[:1900]}}]},
    }


def code_blocks(text: str, language: str = "plain text") -> list[dict[str, Any]]:
    blocks = []
    for offset in range(0, len(text), 1800):
        chunk = text[offset : offset + 1800]
        blocks.append(
            {
                "object": "block",
                "type": "code",
                "code": {
                    "language": language,
                    "rich_text": [{"type": "text", "text": {"content": chunk}}],
                },
            }
        )
    return blocks or [paragraph_block("")]


class NotionAPI:
    """Minimal Notion API wrapper with pagination and retry."""

    def __init__(self, token: str, timeout: int = 60):
        self.token = token
        self.timeout = timeout

    def request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = urllib.request.Request(
            f"{BASE_URL}{path}",
            data=data,
            method=method,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
                "Notion-Version": NOTION_VERSION,
            },
        )
        for attempt in range(3):
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    raw = response.read().decode("utf-8")
                    return json.loads(raw) if raw else {}
            except urllib.error.HTTPError as exc:
                body = exc.read().decode("utf-8", errors="ignore")
                if exc.code in {429, 500, 502, 503, 504} and attempt < 2:
                    time.sleep(2**attempt)
                    continue
                raise RuntimeError(f"Notion API {exc.code}: {body}") from exc
        raise RuntimeError("Notion API retry loop exhausted")

    def create_database(self, parent_page_id: str, title: str, properties: dict[str, Any]) -> str:
        result = self.request(
            "POST",
            "/databases",
            {
                "parent": {"type": "page_id", "page_id": parent_page_id},
                "title": [{"type": "text", "text": {"content": title}}],
                "properties": properties,
            },
        )
        return result["id"]

    def query_database(self, database_id: str, filter_obj: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        pages: list[dict[str, Any]] = []
        payload: dict[str, Any] = {}
        if filter_obj:
            payload["filter"] = filter_obj
        while True:
            result = self.request("POST", f"/databases/{database_id}/query", payload)
            pages.extend(result.get("results", []))
            if not result.get("has_more"):
                return pages
            payload["start_cursor"] = result["next_cursor"]

    def find_page_by_title(self, database_id: str, title_property: str, title: str) -> dict[str, Any] | None:
        results = self.query_database(
            database_id,
            {"property": title_property, "title": {"equals": title}},
        )
        return results[0] if results else None

    def create_page(
        self,
        database_id: str,
        properties: dict[str, Any],
        children: list[dict[str, Any]] | None = None,
    ) -> str:
        payload: dict[str, Any] = {
            "parent": {"database_id": database_id},
            "properties": properties,
        }
        if children:
            payload["children"] = children[:MAX_BLOCKS_PER_REQUEST]
        result = self.request("POST", "/pages", payload)
        page_id = result["id"]
        if children and len(children) > MAX_BLOCKS_PER_REQUEST:
            self.append_blocks(page_id, children[MAX_BLOCKS_PER_REQUEST:])
        return page_id

    def update_page(self, page_id: str, properties: dict[str, Any]) -> None:
        self.request("PATCH", f"/pages/{page_id}", {"properties": properties})

    def list_block_children(self, block_id: str) -> list[dict[str, Any]]:
        blocks: list[dict[str, Any]] = []
        path = f"/blocks/{block_id}/children?page_size=100"
        while True:
            result = self.request("GET", path)
            blocks.extend(result.get("results", []))
            if not result.get("has_more"):
                return blocks
            path = f"/blocks/{block_id}/children?page_size=100&start_cursor={result['next_cursor']}"

    def append_blocks(self, block_id: str, blocks: list[dict[str, Any]]) -> None:
        for offset in range(0, len(blocks), MAX_BLOCKS_PER_REQUEST):
            self.request(
                "PATCH",
                f"/blocks/{block_id}/children",
                {"children": blocks[offset : offset + MAX_BLOCKS_PER_REQUEST]},
            )

    def replace_page_content(self, page_id: str, blocks: list[dict[str, Any]]) -> None:
        for block in self.list_block_children(page_id):
            self.request("DELETE", f"/blocks/{block['id']}")
        if blocks:
            self.append_blocks(page_id, blocks)
