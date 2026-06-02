"""LaTeX paper inspection utilities for Notion sync."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path


SECTION_RE = re.compile(r"\\(?P<kind>section|subsection|subsubsection)\*?\{(?P<title>[^{}]+)\}")
LABEL_RE = re.compile(r"\\label\{([^{}]+)\}")
NEWCOMMAND_RE = re.compile(r"\\newcommand\{\\([a-zA-Z]+)\}\{([^{}]+)\}")


@dataclass(frozen=True)
class PaperSection:
    title: str
    level: int
    source_file: str
    label: str
    content: str
    content_hash: str

    @property
    def summary(self) -> str:
        text = strip_latex(self.content)
        return text[:600].strip()


def strip_latex(text: str, macros: dict[str, str] | None = None) -> str:
    """Return a compact plain-text approximation for summaries."""
    for name, value in (macros or {}).items():
        text = text.replace(f"\\{name}", value)
    text = re.sub(r"%.*", "", text)
    text = re.sub(r"\\cite(?:\[[^\]]*\])?\{([^{}]+)\}", r"[\1]", text)
    text = re.sub(r"\\ref\{([^{}]+)\}", r"\1", text)
    text = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?(?:\{([^{}]*)\})?", r"\1", text)
    text = re.sub(r"[{}$]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_simple_macros(text: str) -> dict[str, str]:
    """Extract simple no-argument macros such as \\newcommand{\\framework}{AsymMark}."""
    return {match.group(1): match.group(2) for match in NEWCOMMAND_RE.finditer(text)}


def extract_title(tex_path: Path) -> str:
    """Extract the first LaTeX title, falling back to the file stem."""
    text = tex_path.read_text(encoding="utf-8", errors="ignore")
    match = re.search(r"\\title\{([^{}]+)\}", text)
    if not match:
        return tex_path.stem
    return strip_latex(match.group(1), extract_simple_macros(text))


def extract_sections(tex_path: Path) -> list[PaperSection]:
    """Extract top-level LaTeX section spans from a .tex file."""
    text = tex_path.read_text(encoding="utf-8", errors="ignore")
    matches = list(SECTION_RE.finditer(text))
    sections: list[PaperSection] = []
    level_by_kind = {"section": 1, "subsection": 2, "subsubsection": 3}

    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        content = text[start:end].strip()
        label_match = LABEL_RE.search(content)
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
        sections.append(
            PaperSection(
                title=strip_latex(match.group("title")),
                level=level_by_kind[match.group("kind")],
                source_file=tex_path.name,
                label=label_match.group(1) if label_match else "",
                content=content,
                content_hash=digest,
            )
        )

    return sections
