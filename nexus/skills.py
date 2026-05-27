"""Claude Code skills catalog for Nexus."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import yaml

from . import SKILLS_DIR

logger = logging.getLogger(__name__)

# Known repo skill directory markers
REPO_SKILL_MARKERS = {
    ".bmad": "bmad",
    ".agents": "agents",
}

# Manual override: entry name → package slug
SKILL_PACKAGE_MAP: dict[str, str] = {}

# Minimum entries with same prefix to trigger grouping
_GROUP_THRESHOLD = 3

# Patchable path for testing (avoids reading real ~/.claude/settings.json)
_CLAUDE_SETTINGS_PATH: Path | None = None


@dataclass
class SkillEntry:
    title: str = ""
    slug: str = ""
    scope: str = "global"  # "global" or "repo"
    url: str | None = None
    added: str = ""
    content: str = ""


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    meta = yaml.safe_load(parts[1]) or {}
    content = parts[2].strip()
    return meta, content


def _render_frontmatter(entry: SkillEntry) -> str:
    meta: dict = {"title": entry.title}
    if entry.slug:
        meta["slug"] = entry.slug
    meta["scope"] = entry.scope
    if entry.url:
        meta["url"] = entry.url
    if entry.added:
        meta["added"] = entry.added
    fm = yaml.dump(meta, default_flow_style=False, allow_unicode=True, sort_keys=False).strip()
    body = entry.content.strip()
    if body:
        return f"---\n{fm}\n---\n\n{body}\n"
    return f"---\n{fm}\n---\n"


def load_skills() -> list[SkillEntry]:
    if not SKILLS_DIR.exists():
        return []
    entries = []
    for md_file in sorted(SKILLS_DIR.glob("*.md")):
        text = md_file.read_text(encoding="utf-8")
        meta, content = _parse_frontmatter(text)
        entries.append(
            SkillEntry(
                title=str(meta.get("title", md_file.stem)),
                slug=str(meta.get("slug", md_file.stem)),
                scope=str(meta.get("scope", "global")),
                url=meta.get("url"),
                added=str(meta.get("added", "")),
                content=content,
            )
        )
    return entries


def save_skill_entry(entry: SkillEntry) -> None:
    SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    path = SKILLS_DIR / f"{entry.slug}.md"
    path.write_text(_render_frontmatter(entry), encoding="utf-8")


def resolve_skill(query: str) -> tuple[SkillEntry | None, list[SkillEntry]]:
    entries = load_skills()
    if not entries:
        return None, []
    # Exact slug
    for e in entries:
        if e.slug == query:
            return e, []
    # Exact title
    ql = query.lower()
    for e in entries:
        if e.title.lower() == ql:
            return e, []
    # Partial
    partial = [
        e for e in entries
        if ql in e.title.lower() or ql in e.slug.lower()
    ]
    if len(partial) == 1:
        return partial[0], []
    return None, partial


def remove_skill(slug: str) -> bool:
    path = SKILLS_DIR / f"{slug}.md"
    if path.exists():
        path.unlink()
        return True
    return False


def version_key(v: str) -> tuple[int, ...]:
    try:
        return tuple(int(x) for x in v.split("."))
    except (ValueError, AttributeError):
        return (0,)


def detect_global_skills(plugins_path: Path | None = None) -> list[dict]:
    if plugins_path is None:
        plugins_path = Path.home() / ".claude" / "plugins"
    cache_dir = plugins_path / "cache"
    if not cache_dir.exists():
        logger.warning("Claude plugins cache not found at %s", cache_dir)
        return []
    results = []
    for org_dir in cache_dir.iterdir():
        if not org_dir.is_dir():
            continue
        for skill_dir in org_dir.iterdir():
            if not skill_dir.is_dir():
                continue
            versions = []
            for v_dir in skill_dir.iterdir():
                if v_dir.is_dir() and v_dir.name[0].isdigit():
                    versions.append(v_dir.name)
            if versions:
                latest = max(versions, key=version_key)
                results.append({
                    "slug": skill_dir.name,
                    "version": latest,
                })
    return results


def _safe_exists(p: Path) -> bool:
    try:
        return p.exists()
    except OSError:
        return False


def _safe_is_dir(p: Path) -> bool:
    try:
        return p.is_dir()
    except OSError:
        return False


def detect_repo_skills(project_path: str) -> list[dict]:
    root = Path(project_path)
    if not _safe_exists(root):
        return []
    results = []
    for marker, slug in REPO_SKILL_MARKERS.items():
        if _safe_exists(root / marker):
            version = _detect_repo_skill_version(root / marker)
            results.append({"slug": slug, "version": version})
    return results


def _detect_repo_skill_version(skill_path: Path) -> str:
    pkg = skill_path / "package.json"
    if pkg.exists():
        import json
        try:
            data = json.loads(pkg.read_text())
            return data.get("version", "unknown")
        except (json.JSONDecodeError, KeyError):
            pass
    return "unknown"



def detect_skills_for_scan(
    projects: list[dict],
    existing_skills: dict,
    hostname: str,
    settings_path: Path | None = None,
) -> dict:
    """Detect global and repo skills, return updated dict for data.json.

    Args:
        projects: list of project dicts (with 'slug' and 'path').
        existing_skills: skills dict from existing data.json.
        hostname: local machine hostname.
        settings_path: path to ~/.claude/settings.json (for testing).

    Returns:
        dict keyed by slug with title, url, presence.
    """
    import json as _json
    from .environment import resolve_path_for_entry
    from .project_config import resolve_project_path

    detected: dict[str, dict] = {}  # slug -> {title, url, presence}

    # --- Step 1: Global plugins from settings.json ---
    if settings_path is None:
        settings_path = _CLAUDE_SETTINGS_PATH or (Path.home() / ".claude" / "settings.json")
    global_slugs: set[str] = set()
    if settings_path.exists():
        try:
            settings = _json.loads(settings_path.read_text(encoding="utf-8"))
            enabled = settings.get("enabledPlugins", {})
            for key, value in enabled.items():
                if value is not True:
                    continue
                slug = key.split("@")[0] if "@" in key else key
                global_slugs.add(slug)
                prev = existing_skills.get(slug, {})
                detected[slug] = {
                    "title": prev.get("title", slug),
                    "url": prev.get("url"),
                    "presence": {
                        **{k: v for k, v in prev.get("presence", {}).items() if k != hostname},
                        hostname: {"global": True},
                    },
                }
        except (_json.JSONDecodeError, OSError, TypeError, AttributeError):
            pass

    # --- Step 2: Repo skills from .agents/skills/ and .claude/skills/ ---
    for proj in projects:
        proj_slug = proj.get("slug", "")
        proj_path = proj.get("path", "")
        if not proj_slug or not proj_path:
            continue
        resolved = resolve_path_for_entry(proj_slug, proj_path)
        if not resolved:
            continue
        resolved = resolve_project_path(resolved)
        root = Path(resolved)
        if not _safe_exists(root):
            continue

        seen_in_project: set[str] = set()

        # .agents/skills/ — group by package
        agents_dir = root / ".agents" / "skills"
        if _safe_is_dir(agents_dir):
            for skill_slug in _group_agents_skills(agents_dir):
                if skill_slug in global_slugs or skill_slug in seen_in_project:
                    continue
                seen_in_project.add(skill_slug)
                _add_repo_presence(detected, existing_skills, skill_slug, proj_slug, hostname)

        # .claude/skills/ — also group by package (same logic as .agents/)
        claude_dir = root / ".claude" / "skills"
        if _safe_is_dir(claude_dir):
            for skill_slug in _group_agents_skills(claude_dir):
                if skill_slug in global_slugs or skill_slug in seen_in_project:
                    continue
                seen_in_project.add(skill_slug)
                _add_repo_presence(detected, existing_skills, skill_slug, proj_slug, hostname)

    return detected


def _group_agents_skills(agents_dir: Path) -> list[str]:
    """Group .agents/skills/ entries by package prefix with threshold.

    If a prefix has >= _GROUP_THRESHOLD entries, collapse to prefix.
    Otherwise keep full name.
    """
    from collections import Counter

    entries = sorted(e.name for e in agents_dir.iterdir() if e.is_dir())
    if not entries:
        return []

    # Count by prefix
    prefix_counts: Counter[str] = Counter()
    for name in entries:
        prefix = SKILL_PACKAGE_MAP.get(name)
        if prefix is None:
            prefix = name.split("-")[0] if "-" in name else name
        prefix_counts[prefix] += 1

    # Build result
    result_set: set[str] = set()
    for name in entries:
        prefix = SKILL_PACKAGE_MAP.get(name)
        if prefix is None:
            prefix = name.split("-")[0] if "-" in name else name
        if prefix_counts[prefix] >= _GROUP_THRESHOLD:
            result_set.add(prefix)
        else:
            result_set.add(name)

    return sorted(result_set)


def _add_repo_presence(
    detected: dict, existing_skills: dict,
    skill_slug: str, proj_slug: str, hostname: str,
) -> None:
    """Add or update a repo skill presence entry.

    Note: callers must ensure skill_slug is NOT a global skill
    (global dedup happens in detect_skills_for_scan before calling this).
    """
    if skill_slug in detected:
        entry = detected[skill_slug]
        host_data = entry["presence"].get(hostname)
        if host_data:
            repos = host_data.get("repos", [])
            if proj_slug not in repos:
                repos.append(proj_slug)
                host_data["repos"] = repos
        else:
            entry["presence"][hostname] = {"global": False, "repos": [proj_slug]}
    else:
        prev = existing_skills.get(skill_slug, {})
        detected[skill_slug] = {
            "title": prev.get("title", skill_slug),
            "url": prev.get("url"),
            "presence": {
                **{k: v for k, v in prev.get("presence", {}).items() if k != hostname},
                hostname: {"global": False, "repos": [proj_slug]},
            },
        }
