from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import yaml

from . import DATA_JSON, LOCK_FILE, file_lock
from .slug import slugify

CODEX_DIR = Path(__file__).resolve().parent.parent / "data" / "codex"


@dataclass
class CodexEntry:
    slug: str = ""
    title: str = ""
    kind: str = "referência"
    domain: str = "pessoal"
    order: int | None = None
    created: str = ""
    updated: str = ""
    content: str = ""


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Parse YAML frontmatter from markdown text. Returns (metadata, content)."""
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    meta = yaml.safe_load(parts[1]) or {}
    content = parts[2].strip()
    return meta, content


def _render_frontmatter(entry: CodexEntry) -> str:
    """Render a CodexEntry back to markdown with YAML frontmatter."""
    meta: dict = {"title": entry.title}
    if entry.kind:
        meta["kind"] = entry.kind
    if entry.domain:
        meta["domain"] = entry.domain
    if entry.order is not None:
        meta["order"] = entry.order
    if entry.created:
        meta["created"] = entry.created
    if entry.updated:
        meta["updated"] = entry.updated

    fm = yaml.dump(meta, default_flow_style=False, allow_unicode=True, sort_keys=False).strip()
    content = entry.content or ""
    return f"---\n{fm}\n---\n\n{content}\n"


def ensure_codex_dir() -> None:
    CODEX_DIR.mkdir(parents=True, exist_ok=True)


def load_codex() -> list[CodexEntry]:
    """Read all .md files from data/codex/, parse frontmatter."""
    ensure_codex_dir()
    entries = []
    for md_file in sorted(CODEX_DIR.glob("*.md")):
        text = md_file.read_text(encoding="utf-8")
        meta, content = _parse_frontmatter(text)
        entries.append(CodexEntry(
            slug=md_file.stem,
            title=meta.get("title", md_file.stem),
            kind=meta.get("kind", meta.get("category", "referência")),
            domain=meta.get("domain", "pessoal"),
            order=meta.get("order"),
            created=str(meta["created"]) if "created" in meta else "",
            updated=str(meta["updated"]) if "updated" in meta else "",
            content=content,
        ))
    return entries


def save_codex_entry(entry: CodexEntry) -> None:
    """Write a CodexEntry as a .md file with frontmatter."""
    ensure_codex_dir()
    if not entry.slug:
        entry.slug = slugify(entry.title)
    path = CODEX_DIR / f"{entry.slug}.md"
    path.write_text(_render_frontmatter(entry), encoding="utf-8")


def remove_codex_entry(slug: str) -> CodexEntry | None:
    """Remove a codex entry file. Returns the entry if found, None otherwise."""
    ensure_codex_dir()
    path = CODEX_DIR / f"{slug}.md"
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    meta, content = _parse_frontmatter(text)
    entry = CodexEntry(
        slug=slug,
        title=meta.get("title", slug),
        kind=meta.get("kind", meta.get("category", "referência")),
        domain=meta.get("domain", "pessoal"),
        order=meta.get("order"),
        created=str(meta["created"]) if "created" in meta else "",
        updated=str(meta["updated"]) if "updated" in meta else "",
        content=content,
    )
    path.unlink()
    return entry


def resolve_codex(query: str) -> tuple[CodexEntry | None, list[CodexEntry]]:
    """Resolve codex entry by query. Precedence: exact slug > partial title."""
    q = query.strip()
    if not q:
        return None, []

    entries = load_codex()
    if not entries:
        return None, []

    ql = q.lower()

    # 1. Exact slug match
    for e in entries:
        if e.slug == ql:
            return e, []

    # 2. Exact title match (case-insensitive)
    exact = [e for e in entries if e.title.lower() == ql]
    if len(exact) == 1:
        return exact[0], []
    if len(exact) > 1:
        return None, exact

    # 3. Partial title match (case-insensitive substring)
    partial = [e for e in entries if ql in e.title.lower() or ql in e.slug]
    if len(partial) == 1:
        return partial[0], []
    if len(partial) > 1:
        return None, partial

    return None, []


def sort_codex(entries: list[CodexEntry]) -> list[CodexEntry]:
    """Sort by order ASC (None = infinity), then by title."""
    return sorted(entries, key=lambda e: (
        e.order if e.order is not None else float("inf"),
        e.title.lower(),
    ))


def _codex_to_dict(e: CodexEntry) -> dict:
    """Serialize CodexEntry to dict for data.json."""
    d: dict = {
        "slug": e.slug,
        "title": e.title,
        "kind": e.kind,
        "domain": e.domain,
        "created": e.created,
        "updated": e.updated,
        "content": e.content,
    }
    if e.order is not None:
        d["order"] = e.order
    return d


def _update_codex_in_data_json() -> None:
    """Update only the 'codex' key in data.json without full project scan."""
    from .registry import ensure_bootstrap

    ensure_bootstrap()

    entries = sort_codex(load_codex())
    codex_dicts = [_codex_to_dict(e) for e in entries]

    with file_lock(LOCK_FILE):
        if DATA_JSON.exists():
            data = json.loads(DATA_JSON.read_text(encoding="utf-8"))
        else:
            data = {"version": "3.0", "last_full_scan": None, "current_environment": None,
                    "projects": [], "apps": [], "environments": []}
        data["codex"] = codex_dicts
        DATA_JSON.parent.mkdir(parents=True, exist_ok=True)
        DATA_JSON.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
