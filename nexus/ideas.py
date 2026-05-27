from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import date

import yaml

from . import DATA_JSON, IDEAS_YML, LOCK_FILE, file_lock


@dataclass
class IdeaEntry:
    id: str = ""
    title: str = ""
    description: str = ""
    domain: str = "pessoal"
    priority: str = "medium"
    references: list[str] | None = None
    notes: str | None = None
    created: str = ""


def _generate_id() -> str:
    return uuid.uuid4().hex[:8]


def ensure_ideas_bootstrap() -> None:
    IDEAS_YML.parent.mkdir(parents=True, exist_ok=True)
    if not IDEAS_YML.exists():
        IDEAS_YML.write_text("ideas: []\n", encoding="utf-8")


def load_ideas() -> list[IdeaEntry]:
    ensure_ideas_bootstrap()
    text = IDEAS_YML.read_text(encoding="utf-8")
    data = yaml.safe_load(text) or {}
    raw_list = data.get("ideas") or []
    entries = []
    for item in raw_list:
        if not isinstance(item, dict):
            continue
        entries.append(IdeaEntry(
            id=item.get("id", ""),
            title=item.get("title", ""),
            description=item.get("description", ""),
            domain=item.get("domain", item.get("category", "pessoal")),
            priority=item.get("priority", "medium"),
            references=item.get("references"),
            notes=item.get("notes"),
            created=item.get("created", ""),
        ))
    return entries


def save_ideas(entries: list[IdeaEntry]) -> None:
    """Save ideas to YAML. Uses `is None` checks (not truthiness) to preserve empty lists."""
    ensure_ideas_bootstrap()
    items = []
    for e in entries:
        d: dict = {}
        if e.id:
            d["id"] = e.id
        d["title"] = e.title
        if e.description:
            d["description"] = e.description
        d["domain"] = e.domain
        d["priority"] = e.priority
        if e.references is not None:
            d["references"] = e.references
        if e.notes is not None:
            d["notes"] = e.notes
        if e.created:
            d["created"] = e.created
        items.append(d)
    data = {"ideas": items}
    IDEAS_YML.write_text(
        yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def sort_ideas(entries: list[IdeaEntry]) -> list[IdeaEntry]:
    """Sort by priority (high first) then by created (newest first)."""
    priority_order = {"high": 0, "medium": 1, "low": 2}
    return sorted(
        sorted(entries, key=lambda e: e.created or "", reverse=True),
        key=lambda e: priority_order.get(e.priority, 1),
    )


def add_idea(entry: IdeaEntry) -> IdeaEntry:
    # Category validation is enforced at CLI layer (_prompt_choice with fixed options)
    entry.id = _generate_id()
    if not entry.created:
        entry.created = str(date.today())
    entries = load_ideas()
    entries.append(entry)
    save_ideas(entries)
    return entry


def update_idea(idea_id: str, **kwargs) -> IdeaEntry | None:
    entries = load_ideas()
    for e in entries:
        if e.id == idea_id:
            for k, v in kwargs.items():
                if hasattr(e, k):
                    setattr(e, k, v)
            save_ideas(entries)
            return e
    return None


def remove_idea(idea_id: str) -> IdeaEntry | None:
    entries = load_ideas()
    for i, e in enumerate(entries):
        if e.id == idea_id:
            removed = entries.pop(i)
            save_ideas(entries)
            return removed
    return None


def resolve_idea(query: str) -> tuple[IdeaEntry | None, list[IdeaEntry]]:
    """Resolve idea by query. Precedence: exact ID > exact title > partial title."""
    q = query.strip()
    if not q:
        return None, []

    entries = load_ideas()
    if not entries:
        return None, []

    # 1. Exact ID match (always wins)
    for e in entries:
        if e.id == q:
            return e, []

    ql = q.lower()

    # 2. Exact title match (case-insensitive)
    exact = [e for e in entries if e.title.lower() == ql]
    if len(exact) == 1:
        return exact[0], []
    if len(exact) > 1:
        return None, exact

    # 3. Partial title match (case-insensitive substring)
    partial = [e for e in entries if ql in e.title.lower()]
    if len(partial) == 1:
        return partial[0], []
    if len(partial) > 1:
        return None, partial

    return None, []


def _idea_to_dict(e: IdeaEntry) -> dict:
    """Serialize IdeaEntry to dict for data.json."""
    d: dict = {
        "id": e.id,
        "title": e.title,
        "description": e.description,
        "domain": e.domain,
        "priority": e.priority,
        "created": e.created,
    }
    if e.references is not None:
        d["references"] = e.references
    if e.notes is not None:
        d["notes"] = e.notes
    return d


def _update_ideas_in_data_json() -> None:
    """Update only the 'ideas' key in data.json without full project scan."""
    from .registry import ensure_bootstrap

    ensure_bootstrap()

    ideas = sort_ideas(load_ideas())
    idea_dicts = [_idea_to_dict(e) for e in ideas]

    with file_lock(LOCK_FILE):
        if DATA_JSON.exists():
            data = json.loads(DATA_JSON.read_text(encoding="utf-8"))
        else:
            data = {"version": "3.0", "last_full_scan": None, "current_environment": None,
                    "projects": [], "apps": [], "environments": []}
        data["ideas"] = idea_dicts
        data["version"] = "3.0"
        DATA_JSON.parent.mkdir(parents=True, exist_ok=True)
        DATA_JSON.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
