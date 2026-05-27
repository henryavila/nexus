from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
import json

import yaml

from . import DATA_DIR, DATA_JSON, PROJECTS_YML
from .slug import make_short_slug


@dataclass
class ProjectEntry:
    name: str
    path: str | None = None
    slug: str = ""
    description: str = ""
    icon: str | None = None
    domain: str = "pessoal"
    nature: str = "contexto"
    private: bool = False
    url: str | None = None
    repo: str | None = None
    status: str | None = None
    note: str | None = None
    added: str = ""
    web: dict | None = None


def ensure_bootstrap() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not PROJECTS_YML.exists():
        PROJECTS_YML.write_text("projects: []\n", encoding="utf-8")
    if not DATA_JSON.exists():
        DATA_JSON.write_text(
            json.dumps({"version": "3.0", "last_full_scan": None, "current_environment": None,
                        "projects": [], "apps": [], "environments": [], "ideas": [], "codex": []},
                       indent=2),
            encoding="utf-8",
        )


def normalize_path(path: str) -> str:
    p = Path(path).expanduser().resolve()
    try:
        exists = p.exists()
    except OSError:
        return str(p)
    if not exists:
        return str(p)
    resolved = Path(p.anchor)
    for part in p.relative_to(p.anchor).parts:
        try:
            match = next(
                child.name for child in resolved.iterdir()
                if child.name.lower() == part.lower()
            )
            resolved = resolved / match
        except (StopIteration, PermissionError, OSError):
            resolved = resolved / part
    return str(resolved)


def load_registry() -> list[ProjectEntry]:
    ensure_bootstrap()
    text = PROJECTS_YML.read_text(encoding="utf-8")
    data = yaml.safe_load(text) or {}
    raw_list = data.get("projects") or []
    entries = []
    for item in raw_list:
        if not isinstance(item, dict) or "name" not in item:
            continue
        entries.append(ProjectEntry(
            name=item["name"],
            path=item.get("path"),
            slug=item.get("slug", ""),
            description=item.get("description", ""),
            icon=item.get("icon"),
            domain=item.get("domain", item.get("category", "pessoal")),
            nature=item.get("nature", "contexto"),
            private=item.get("private", False),
            url=item.get("url"),
            repo=item.get("repo"),
            status=item.get("status"),
            note=item.get("note"),
            added=item.get("added", ""),
            web=item.get("web"),
        ))
    return entries


def save_registry(entries: list[ProjectEntry]) -> None:
    ensure_bootstrap()
    items = []
    for e in entries:
        d: dict = {"name": e.name}
        if e.path is not None:
            d["path"] = e.path
        if e.slug:
            d["slug"] = e.slug
        if e.description:
            d["description"] = e.description
        if e.icon:
            d["icon"] = e.icon
        d["domain"] = e.domain
        d["nature"] = e.nature
        if e.private:
            d["private"] = e.private
        if e.url:
            d["url"] = e.url
        if e.repo:
            d["repo"] = e.repo
        if e.status:
            d["status"] = e.status
        if e.note:
            d["note"] = e.note
        if e.added:
            d["added"] = e.added
        if e.web:
            d["web"] = e.web
        items.append(d)
    data = {"projects": items}
    PROJECTS_YML.write_text(
        yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def add_project(entry: ProjectEntry) -> tuple[bool, ProjectEntry]:
    norm = normalize_path(entry.path) if entry.path else None
    entries = load_registry()
    if norm:
        for e in entries:
            if e.path and normalize_path(e.path) == norm:
                return False, e
    if norm:
        entry.path = norm
    if not entry.added:
        entry.added = str(date.today())
    if not entry.slug:
        entry.slug = _unique_slug(make_short_slug(entry.name), entries)
    entries.append(entry)
    save_registry(entries)
    return True, entry


def _unique_slug(base_slug: str, entries: list[ProjectEntry]) -> str:
    """Ensure slug is unique among existing project entries and apps."""
    from nexus.apps import load_apps
    existing = {e.slug for e in entries if e.slug}
    app_slugs = {a.slug for a in load_apps()}
    existing |= app_slugs
    if base_slug not in existing:
        return base_slug
    counter = 2
    while f"{base_slug}-{counter}" in existing:
        counter += 1
    return f"{base_slug}-{counter}"


def backfill_slugs() -> int:
    """Generate short slugs for projects that don't have one."""
    entries = load_registry()
    updated = 0
    for e in entries:
        if not e.slug:
            e.slug = _unique_slug(make_short_slug(e.name), entries)
            updated += 1
    if updated:
        save_registry(entries)
    return updated


def update_project(path_or_name: str, **kwargs) -> ProjectEntry | None:
    norm = normalize_path(path_or_name) if path_or_name else None
    entries = load_registry()
    for e in entries:
        if e.path and norm and normalize_path(e.path) == norm:
            for k, v in kwargs.items():
                if hasattr(e, k):
                    setattr(e, k, v)
            save_registry(entries)
            return e
    # Fallback: match by name (for entries without paths)
    for e in entries:
        if e.name == path_or_name:
            for k, v in kwargs.items():
                if hasattr(e, k):
                    setattr(e, k, v)
            save_registry(entries)
            return e
    return None


def remove_project(path_or_name: str) -> bool:
    matched, _ = resolve_project(path_or_name)
    if not matched:
        return False
    if matched.path:
        norm = normalize_path(matched.path)
        entries = [e for e in load_registry() if not e.path or normalize_path(e.path) != norm]
    else:
        # No path — remove by name match
        entries = [e for e in load_registry() if e.name != matched.name]
    save_registry(entries)
    return True


def move_project(old_path: str, new_path: str) -> ProjectEntry | None:
    """Update a project's path in the registry. Returns updated entry or None."""
    norm_old = normalize_path(old_path) if old_path else None
    norm_new = normalize_path(new_path)
    entries = load_registry()
    # Guard: don't allow moving to an already-registered path
    for e in entries:
        if e.path and normalize_path(e.path) == norm_new:
            return None
    for e in entries:
        if e.path and norm_old and normalize_path(e.path) == norm_old:
            e.path = norm_new
            save_registry(entries)
            return e
    return None


def resolve_by_slug_or_path(identifier: str) -> ProjectEntry | None:
    """Strict: exact slug or exact path only. No fuzzy. For hooks."""
    entries = load_registry()
    for e in entries:
        if e.slug and e.slug == identifier:
            return e
    from nexus.environment import find_environment
    env = find_environment()
    if env:
        for slug, path in env.paths.items():
            if path and normalize_path(path) == normalize_path(identifier):
                for e in entries:
                    if e.slug == slug:
                        return e
    for e in entries:
        if e.path and normalize_path(e.path) == normalize_path(identifier):
            return e
    return None


def resolve_project(query: str) -> tuple[ProjectEntry | None, list[ProjectEntry]]:
    entries = load_registry()
    if not entries:
        return None, []

    q = query.strip("\"'").strip()
    if not q:
        return None, []
    ql = q.lower()

    # 0. Exact slug match (case-sensitive — slugs are machine-generated identifiers)
    for e in entries:
        if e.slug and e.slug == q:
            return e, []

    # 1. Exact path match (only for entries with paths)
    for e in entries:
        if e.path and normalize_path(e.path) == normalize_path(q):
            return e, []

    # 2. Exact name match (case-insensitive)
    for e in entries:
        if e.name.lower() == ql:
            return e, []

    # 3. Partial match (name, slug, path — guarded against None path)
    partial = [
        e for e in entries
        if ql in e.name.lower()
        or (e.slug and ql in e.slug.lower())
        or (e.path and ql in e.path.lower())
    ]
    if len(partial) == 1:
        return partial[0], []
    return None, partial
