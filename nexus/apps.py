"""App management for Nexus."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import yaml

from . import APPS_YML, DATA_JSON, LOCK_FILE, file_lock


@dataclass
class AppEntry:
    name: str
    slug: str = ""
    description: str = ""
    icon: str | None = None
    domain: str = "pessoal"
    github: str | None = None
    url: str | None = None
    note: str | None = None
    added: str = ""


def load_apps() -> list[AppEntry]:
    if not APPS_YML.exists():
        return []
    with open(APPS_YML, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not data or "apps" not in data:
        return []
    entries = []
    for item in data["apps"]:
        if not isinstance(item, dict) or "name" not in item:
            continue
        entries.append(
            AppEntry(
                name=item["name"],
                slug=item.get("slug", ""),
                description=item.get("description", ""),
                icon=item.get("icon"),
                domain=item.get("domain", item.get("category", "pessoal")),
                github=item.get("github"),
                url=item.get("url"),
                note=item.get("note"),
                added=str(item.get("added", "")),
            )
        )
    return entries


def _slugify(name: str) -> str:
    """Convert a name to a URL-safe slug: 'My App' -> 'my-app'."""
    s = name.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_]+", "-", s)
    return s.strip("-")


def add_app(entry: AppEntry) -> AppEntry:
    """Add an app to the registry, generating slug and added date if needed."""
    entries = load_apps()
    if not entry.slug:
        # Deferred import to avoid circular dependency
        from nexus.registry import _unique_slug
        base = _slugify(entry.name)
        entry.slug = _unique_slug(base, [])
    if not entry.added:
        entry.added = date.today().isoformat()
    entries.append(entry)
    save_apps(entries)
    _update_apps_in_data_json()
    return entry


def resolve_app(query: str) -> tuple[AppEntry | None, list[AppEntry]]:
    """Resolve a query to an app entry.

    Resolution order:
    1. Exact slug match
    2. Exact name match (case-insensitive)
    3. Partial match (substring in name or slug)

    Returns (entry, []) on unique match, (None, candidates) on ambiguous/none.
    """
    entries = load_apps()
    if not entries:
        return None, []
    # Exact slug match
    for e in entries:
        if e.slug and e.slug == query:
            return e, []
    # Exact name match (case-insensitive)
    ql = query.lower()
    for e in entries:
        if e.name.lower() == ql:
            return e, []
    # Partial match
    partial = [
        e for e in entries
        if ql in e.name.lower() or (e.slug and ql in e.slug.lower())
    ]
    if len(partial) == 1:
        return partial[0], []
    return None, partial


def remove_app(slug: str) -> bool:
    """Remove an app by slug. Returns True if removed, False if not found."""
    entries = load_apps()
    new_entries = [e for e in entries if e.slug != slug]
    if len(new_entries) == len(entries):
        return False
    save_apps(new_entries)
    _update_apps_in_data_json()
    return True



def _update_apps_in_data_json() -> None:
    """Update only the 'apps' key in data.json without full project scan."""
    apps = load_apps()
    app_dicts = [
        {"name": a.name, "slug": a.slug, "description": a.description,
         "icon": a.icon, "domain": a.domain, "github": a.github,
         "url": a.url}
        for a in apps
    ]

    with file_lock(LOCK_FILE):
        if DATA_JSON.exists():
            data = json.loads(DATA_JSON.read_text(encoding="utf-8"))
        else:
            data = {"version": "3.0", "last_full_scan": None, "current_environment": None,
                    "projects": [], "apps": [], "environments": [], "skills": {}}
        data["apps"] = app_dicts
        data["version"] = "3.0"
        DATA_JSON.parent.mkdir(parents=True, exist_ok=True)
        DATA_JSON.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")



def save_apps(entries: list[AppEntry]) -> None:
    data = []
    for e in entries:
        d: dict = {"name": e.name, "slug": e.slug}
        if e.description:
            d["description"] = e.description
        if e.icon:
            d["icon"] = e.icon
        d["domain"] = e.domain
        if e.github:
            d["github"] = e.github
        if e.url:
            d["url"] = e.url
        if e.note:
            d["note"] = e.note
        if e.added:
            d["added"] = e.added
        data.append(d)
    APPS_YML.parent.mkdir(parents=True, exist_ok=True)
    with open(APPS_YML, "w", encoding="utf-8") as f:
        yaml.dump(
            {"apps": data},
            f,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        )
