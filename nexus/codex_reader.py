from __future__ import annotations

from dataclasses import dataclass
import re


_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)(?:\s+#+\s*)?$")
_FENCE_RE = re.compile(r"^(```+|~~~+)")
_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")


@dataclass(frozen=True)
class CodexSection:
    level: int
    title: str
    line_index: int


def extract_markdown_sections(content: str) -> list[CodexSection]:
    sections: list[CodexSection] = []
    in_fence = False

    for line_index, line in enumerate(content.splitlines()):
        if _FENCE_RE.match(line.strip()):
            in_fence = not in_fence
            continue
        if in_fence:
            continue

        match = _HEADING_RE.match(line)
        if not match:
            continue

        hashes, raw_title = match.groups()
        title = raw_title.strip()
        if not title:
            continue
        sections.append(CodexSection(level=len(hashes), title=title, line_index=line_index))

    return sections


def format_section_label(section: CodexSection) -> str:
    indent = "  " * max(section.level - 1, 0)
    return f"{indent}{'#' * section.level} {section.title}"


def extract_images(content: str) -> list[tuple[str, str]]:
    """Extract (alt_text, relative_path) tuples from markdown image references."""
    return _IMAGE_RE.findall(content)


def replace_images_with_placeholders(content: str) -> str:
    """Replace ``![alt](path)`` with a visible placeholder line."""
    def _replacer(m: re.Match) -> str:
        alt = m.group(1) or "imagem"
        return f"  🖼  {alt}  — aperte `v` para visualizar"
    return _IMAGE_RE.sub(_replacer, content)


def slice_markdown_from_section(
    content: str,
    sections: list[CodexSection],
    section_index: int | None,
) -> str:
    if section_index is None:
        return content
    if section_index < 0 or section_index >= len(sections):
        return content

    lines = content.splitlines()
    start = sections[section_index].line_index
    return "\n".join(lines[start:]).rstrip() + "\n"
