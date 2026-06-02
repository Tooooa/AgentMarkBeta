"""Convert LaTeX paper source into readable Notion blocks."""

from __future__ import annotations

import re

from .latex import extract_simple_macros, extract_title, strip_latex
from .notion_api import code_blocks, heading_block, paragraph_block


SECTION_RE = re.compile(r"\\(?P<kind>section|subsection|subsubsection)\*?\{(?P<title>[^{}]+)\}")
BEGIN_ENV_RE = re.compile(r"\\begin\{([^{}]+)\}")
END_ENV_RE = re.compile(r"\\end\{([^{}]+)\}")
TABLE_ENVS = {"table", "table*", "tabular", "tabular*", "tabularx", "longtable"}


def _document_body(text: str) -> str:
    match = re.search(r"\\begin\{document\}(.*)\\end\{document\}", text, flags=re.S)
    return match.group(1) if match else text


def _replace_macros(text: str, macros: dict[str, str]) -> str:
    for name, value in macros.items():
        text = re.sub(rf"\\{re.escape(name)}\s*\{{\}}", value, text)
        text = text.replace(f"\\{name}", value)
    return text


def _plain_text(text: str, macros: dict[str, str]) -> str:
    text = _replace_macros(text, macros)
    text = re.sub(r"\\label\{[^{}]+\}", "", text)
    text = re.sub(r"\\cite(?:\[[^\]]*\])?\{([^{}]+)\}", r"[\1]", text)
    text = re.sub(r"\\(?:ref|autoref|cref)\{([^{}]+)\}", r"\1", text)
    text = re.sub(r"\\(textbf|textit|emph|underline|texttt)\{([^{}]*)\}", r"\2", text)
    text = re.sub(r"\\item\s*", "- ", text)
    return strip_latex(text, macros)


def _flush_paragraph(blocks: list[dict], lines: list[str], macros: dict[str, str]) -> None:
    if not lines:
        return
    text = _plain_text(" ".join(lines), macros)
    lines.clear()
    if not text:
        return
    for offset in range(0, len(text), 1800):
        blocks.append(paragraph_block(text[offset : offset + 1800]))


def _heading_level(kind: str) -> int:
    return {"section": 1, "subsection": 2, "subsubsection": 3}[kind]


def latex_to_plain_notion_blocks(text: str, macros: dict[str, str] | None = None) -> list[dict]:
    """Convert LaTeX into Notion blocks: headings/prose, with tables kept as LaTeX."""
    macros = {**extract_simple_macros(text), **(macros or {})}
    body = _document_body(text)
    lines = body.splitlines()
    blocks: list[dict] = []
    paragraph_lines: list[str] = []
    table_lines: list[str] | None = None
    table_env: str | None = None
    in_abstract = False

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            _flush_paragraph(blocks, paragraph_lines, macros)
            continue
        if line.startswith("%"):
            continue
        if line in {r"\maketitle"} or line.startswith(r"\title{") or line.startswith(r"\newcommand{"):
            continue

        if table_lines is not None:
            table_lines.append(raw_line)
            end_match = END_ENV_RE.search(line)
            if end_match and end_match.group(1) == table_env:
                _flush_paragraph(blocks, paragraph_lines, macros)
                blocks.extend(code_blocks("\n".join(table_lines).strip(), language="latex"))
                table_lines = None
                table_env = None
            continue

        begin_match = BEGIN_ENV_RE.search(line)
        if begin_match:
            env = begin_match.group(1)
            if env == "abstract":
                _flush_paragraph(blocks, paragraph_lines, macros)
                blocks.append(heading_block("Abstract", 1))
                in_abstract = True
                continue
            if env in TABLE_ENVS:
                _flush_paragraph(blocks, paragraph_lines, macros)
                table_env = env
                table_lines = [raw_line]
                continue

        end_match = END_ENV_RE.search(line)
        if end_match and end_match.group(1) == "abstract":
            _flush_paragraph(blocks, paragraph_lines, macros)
            in_abstract = False
            continue

        section_match = SECTION_RE.match(line)
        if section_match and not in_abstract:
            _flush_paragraph(blocks, paragraph_lines, macros)
            blocks.append(
                heading_block(
                    _plain_text(section_match.group("title"), macros),
                    _heading_level(section_match.group("kind")),
                )
            )
            remainder = line[section_match.end() :].strip()
            if remainder:
                paragraph_lines.append(remainder)
            continue

        paragraph_lines.append(line)

    _flush_paragraph(blocks, paragraph_lines, macros)
    return blocks


def paper_text_blocks(tex_path) -> tuple[str, list[dict]]:
    text = tex_path.read_text(encoding="utf-8", errors="ignore")
    title = extract_title(tex_path)
    return title, [heading_block(title, 1), *latex_to_plain_notion_blocks(text)]
