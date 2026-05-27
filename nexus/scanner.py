from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
import json
import os
import re
import subprocess

from . import DATA_JSON, EXCLUDED_DIRS, LOCK_FILE, file_lock
from .environment import find_environment, get_current_hostname, resolve_path_for_entry, update_last_seen
from .project_config import apply_project_overrides, resolve_project_path
from .registry import load_registry, normalize_path, resolve_by_slug_or_path


def _run(cmd: list[str], cwd: str) -> str:
    out = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if out.returncode != 0:
        return ""
    return out.stdout.strip()


def _safe_exists(p: Path) -> bool:
    try:
        return p.exists()
    except OSError:
        return False


def _git_data(root: Path) -> dict | None:
    if not _safe_exists(root / ".git"):
        return None
    cwd = str(root)
    branch = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd)
    last_commit_date = _run(["git", "log", "-1", "--format=%cs"], cwd)
    last_commit_msg = _run(["git", "log", "-1", "--format=%s"], cwd)
    dirty = bool(_run(["git", "status", "--porcelain"], cwd))

    remote = _run(["git", "remote", "get-url", "origin"], cwd)
    repo = None
    if "github.com" in remote:
        m = re.search(r"github\.com[:/]([^/]+/[^/.]+)", remote)
        if m:
            repo = m.group(1)

    return {
        "branch": branch or None,
        "last_commit_date": last_commit_date or None,
        "last_commit_message": last_commit_msg or None,
        "dirty": dirty,
        "repo": repo,
    }


def _filesystem_last_modified(root: Path, max_depth: int = 3) -> dict:
    last_file = None
    last_ts = 0.0
    root_depth = str(root).count(os.sep)
    for dirpath, dirnames, filenames in os.walk(root):
        depth = str(dirpath).count(os.sep) - root_depth
        if depth >= max_depth:
            dirnames.clear()
            continue
        dirnames[:] = [d for d in dirnames if d not in EXCLUDED_DIRS]
        for fname in filenames:
            fpath = Path(dirpath) / fname
            try:
                mtime = fpath.stat().st_mtime
            except OSError:
                continue
            if mtime > last_ts:
                last_ts = mtime
                last_file = str(fpath.relative_to(root))
    return {
        "last_modified_file": last_file,
        "last_modified_date": datetime.fromtimestamp(last_ts).date().isoformat() if last_ts else None,
    }


def _check_claude_memory(root: Path) -> bool | None:
    """Check if Claude memory is portable (inside project) vs local.

    Returns:
        True  = memory is inside project (portable)
        False = memory is only in ~/.claude (local, not portable)
        None  = no memory found anywhere (neutral)

    .claude/memory/ is excluded — it's a Claude Code artifact.
    If ~/.claude/projects/{encoded}/memory is a symlink into the project,
    that counts as portable (Claude Code mirrors the portable location).
    """
    # 1. Check for portable memory dirs (NOT .claude/memory — that's a Claude Code artifact)
    portable_dirs = [
        root / ".memory",
        root / "memoria",
        root / "MEMORY",
        root / "memory",
    ]
    if any(d.is_dir() for d in portable_dirs):
        return True

    # 2. Search for MEMORY.md / MEMORIA.md files (bounded depth, skip excluded dirs)
    _memory_filenames = {"MEMORY.md", "MEMORIA.md", "MEMORIa.md"}
    root_depth = str(root).count(os.sep)
    for dirpath, dirnames, filenames in os.walk(root):
        depth = str(dirpath).count(os.sep) - root_depth
        if depth >= 4:
            dirnames.clear()
            continue
        dirnames[:] = [d for d in dirnames if d not in EXCLUDED_DIRS and d != ".claude"]
        if _memory_filenames & set(filenames):
            return True

    # 3. Check ~/.claude/projects/{encoded}/memory/
    home_claude = Path.home() / ".claude" / "projects"
    if home_claude.exists():
        norm = normalize_path(str(root))
        encoded = norm.replace("/", "-").replace(" ", "-")
        local_memory = home_claude / encoded / "memory"
        if local_memory.exists():
            # Symlink pointing inside the project = portable
            if local_memory.is_symlink():
                try:
                    target = local_memory.resolve()
                    if str(target).startswith(str(root.resolve())):
                        return True
                except OSError:
                    pass
            return False

    return None


def scan_project(path: str) -> dict | None:
    resolved = resolve_project_path(normalize_path(path))
    p = Path(resolved)
    if not _safe_exists(p) or not p.is_dir():
        return None

    git = _git_data(p)
    project_class = "git" if git else "filesystem"

    fs_data = _filesystem_last_modified(p)
    commit_date = git.get("last_commit_date") if git else None
    fs_date = fs_data.get("last_modified_date")

    # Use the most recent between commit and filesystem
    if commit_date and fs_date:
        last_activity = max(commit_date, fs_date)
    else:
        last_activity = commit_date or fs_date

    if project_class == "git":
        fs_data = None

    memory_check = _check_claude_memory(p)
    web_compliant = None

    return {
        "class": project_class,
        "last_activity": last_activity,
        "git": git,
        "filesystem": fs_data,
        "health": {
            "path_exists": True,
            "claude_memory_portable": memory_check,
            "web_compliant": web_compliant,
        },
        "last_scanned": datetime.now().isoformat(timespec="seconds"),
    }


def _merge_scan_with_registry(entry, scan_data: dict) -> dict:
    """Merge registry entry (manual) with scan data (auto) for data.json."""
    git = scan_data.get("git")

    status = entry.status or "active"

    repo = entry.repo
    if not repo and git and git.get("repo"):
        repo = git.get("repo")
    git_clean = {k: v for k, v in git.items() if k != "repo"} if git else None

    web_info = None
    if entry.web and entry.path:
        resolved = resolve_path_for_entry(entry.slug, entry.path)
        static_dir = Path(resolve_project_path(resolved or entry.path)) / entry.web.get("static_dir", "")
        has_output = _safe_exists(static_dir) and any(static_dir.iterdir()) if _safe_exists(static_dir) else False
        web_info = {
            "route": entry.web.get("route"),
            "has_output": has_output,
        }
        scan_data["health"]["web_compliant"] = has_output

    return {
        "name": entry.name,
        "slug": entry.slug,
        "path": entry.path,
        "description": entry.description,
        "icon": entry.icon,
        "domain": entry.domain,
        "nature": entry.nature,
        "private": entry.private,
        "url": entry.url,
        "repo": repo,
        "status": status,
        "note": entry.note,
        "class": scan_data["class"],
        "last_activity": scan_data["last_activity"],
        "git": git_clean,
        "filesystem": scan_data.get("filesystem"),
        "health": scan_data["health"],
        "web": web_info,
        "last_scanned": scan_data["last_scanned"],
    }


def get_health_value(health: dict, key: str, hostname: str | None = None) -> bool | None:
    """Get a health value, handling both per-env dict and legacy flat format.

    Per-env format: {"path_exists": {"HOST-A": true, "HOST-B": false}}
    Flat format:    {"path_exists": true}
    """
    val = health.get(key)
    if isinstance(val, dict):
        if hostname is None:
            from .environment import get_current_hostname
            hostname = get_current_hostname()
        return val.get(hostname)
    return val  # Flat format (backward compat)


def _merge_health_per_env(existing_item: dict, new_scan: dict, hostname: str) -> None:
    """Merge new scan health into existing per-env health structure."""
    old_health = existing_item.get("health", {})
    new_health = new_scan.get("health", {})
    for key in ["path_exists", "claude_memory_portable", "web_compliant"]:
        new_val = new_health.get(key)
        if isinstance(old_health.get(key), dict):
            old_health[key][hostname] = new_val
        else:
            old_health[key] = {hostname: new_val}
    existing_item["health"] = old_health


def _read_data() -> dict:
    if not DATA_JSON.exists():
        return {
            "version": "3.0",
            "last_full_scan": None,
            "current_environment": None,
            "projects": [],
            "apps": [],
            "environments": [],
            "ideas": [],
            "codex": [],
        }
    with open(DATA_JSON, encoding="utf-8") as f:
        data = json.load(f)
    # Upgrade v2.x to v3.0 structure
    if data.get("version") != "3.0":
        data["version"] = "3.0"
        data.setdefault("current_environment", None)
        data.setdefault("apps", [])
        data.setdefault("environments", [])
        data.setdefault("ideas", [])
        data.setdefault("codex", [])
    return data


def _write_data(data: dict) -> None:
    DATA_JSON.parent.mkdir(parents=True, exist_ok=True)
    DATA_JSON.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def scan_all(on_progress=None, cancelled=None) -> dict:
    hostname = get_current_hostname()
    env = find_environment(hostname)
    if env:
        update_last_seen(hostname)

    # Read existing data to preserve other envs' health
    existing_data = _read_data()
    existing_by_slug = {}
    for p in existing_data.get("projects", []):
        slug = p.get("slug")
        if slug:
            existing_by_slug[slug] = p

    entries = load_registry()
    total = len(entries)
    projects = [None] * total
    was_cancelled = False

    def _process_entry(index, entry):
        """Scan a single project entry (runs in thread pool)."""
        effective_entry = apply_project_overrides(entry)
        resolved = resolve_path_for_entry(entry.slug, entry.path)
        scan_data = scan_project(resolved) if resolved else None
        if scan_data is None:
            merged = {
                "name": effective_entry.name,
                "slug": effective_entry.slug,
                "path": effective_entry.path,
                "description": effective_entry.description,
                "icon": effective_entry.icon,
                "domain": effective_entry.domain,
                "nature": effective_entry.nature,
                "private": effective_entry.private,
                "url": effective_entry.url,
                "repo": effective_entry.repo,
                "status": effective_entry.status or "active",
                "note": effective_entry.note,
                "class": "unknown",
                "last_activity": None,
                "git": None,
                "filesystem": None,
                "health": {"path_exists": False, "claude_memory_portable": None, "web_compliant": None},
                "web": None,
                "last_scanned": datetime.now().isoformat(timespec="seconds"),
            }
        else:
            merged = _merge_scan_with_registry(effective_entry, scan_data)

        # Merge health per-env: preserve other hostnames' data
        # Thread-safe: each slug maps to a unique dict in existing_by_slug
        existing = existing_by_slug.get(effective_entry.slug)
        if existing:
            _merge_health_per_env(existing, merged, hostname)
            merged["health"] = existing["health"]
        else:
            # New entry: wrap health in per-env dict
            wrapper = {}
            _merge_health_per_env(wrapper, merged, hostname)
            merged["health"] = wrapper["health"]

        return index, effective_entry.name, merged

    completed_count = 0
    max_workers = min(total, 32) if total > 0 else 1

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {}
        for i, entry in enumerate(entries):
            if cancelled and cancelled():
                was_cancelled = True
                break
            futures[executor.submit(_process_entry, i, entry)] = i

        if not was_cancelled:
            for future in as_completed(futures):
                if cancelled and cancelled():
                    was_cancelled = True
                    break
                try:
                    idx, name, merged = future.result()
                except Exception:
                    continue
                projects[idx] = merged
                completed_count += 1
                if on_progress:
                    on_progress(completed_count, total, name)

        if was_cancelled:
            executor.shutdown(wait=False, cancel_futures=True)

    projects = [p for p in projects if p is not None]

    # Cancelled scan: preserve existing data.json (don't overwrite with partial data)
    if was_cancelled:
        return existing_data

    # Include ideas in data.json
    from .ideas import load_ideas, sort_ideas, _idea_to_dict
    ideas = sort_ideas(load_ideas())
    idea_dicts = [_idea_to_dict(e) for e in ideas]

    # Include codex in data.json
    from .codex import load_codex, sort_codex, _codex_to_dict
    codex_entries = sort_codex(load_codex())
    codex_dicts = [_codex_to_dict(e) for e in codex_entries]

    # Load apps for data.json
    from .apps import load_apps
    apps = load_apps()
    app_dicts = [{"name": a.name, "slug": a.slug, "description": a.description,
                  "icon": a.icon, "domain": a.domain, "github": a.github,
                  "url": a.url} for a in apps]

    # Load environments for data.json
    from .environment import load_environments
    env_entries = load_environments()
    env_dicts = [{"hostname": e.hostname, "name": e.name, "location": e.location,
                  "last_seen": e.last_seen} for e in env_entries]

    data = {
        "version": "3.0",
        "last_full_scan": datetime.now().isoformat(timespec="seconds"),
        "current_environment": hostname,
        "projects": projects,
        "apps": app_dicts,
        "environments": env_dicts,
        "ideas": idea_dicts,
        "codex": codex_dicts,
    }
    with file_lock(LOCK_FILE):
        _write_data(data)
    return data


def scan_one(identifier: str) -> dict | None:
    # Resolve by slug or path (strict)
    entry = resolve_by_slug_or_path(identifier)
    if not entry:
        # Fallback: try path-based lookup for backward compat
        target = normalize_path(identifier)
        entries = load_registry()
        for e in entries:
            if not e.path:
                continue
            env_resolved = resolve_path_for_entry(e.slug, e.path)
            registry_path = normalize_path(e.path)
            resolved_path = normalize_path(resolve_project_path(env_resolved or e.path))
            if target in {registry_path, resolved_path}:
                entry = e
                break
    if not entry:
        return None

    hostname = get_current_hostname()
    effective_entry = apply_project_overrides(entry)
    scan_path = resolve_path_for_entry(entry.slug, entry.path)
    scan_data = scan_project(scan_path) if scan_path else None
    if scan_data is None:
        return None

    merged = _merge_scan_with_registry(effective_entry, scan_data)

    with file_lock(LOCK_FILE):
        data = _read_data()
        projects = data.get("projects", [])
        replaced = False

        # Match by slug (preferred) or path
        registry_target = normalize_path(entry.path) if entry.path else ""
        resolved_target = normalize_path(resolve_project_path(scan_path or entry.path)) if (scan_path or entry.path) else ""
        for idx, p in enumerate(projects):
            slug_match = entry.slug and p.get("slug") == entry.slug
            current = normalize_path(p.get("path", ""))
            path_match = current and current in {registry_target, resolved_target}
            if slug_match or path_match:
                # Don't regress last_activity (stale OneDrive scan protection)
                existing_activity = p.get("last_activity")
                new_activity = merged.get("last_activity")
                if existing_activity and new_activity and existing_activity > new_activity:
                    merged["last_activity"] = existing_activity
                # Merge health per-env
                _merge_health_per_env(p, merged, hostname)
                merged["health"] = p["health"]
                projects[idx] = merged
                replaced = True
                break
        if not replaced:
            # New entry: wrap health in per-env dict
            wrapper = {}
            _merge_health_per_env(wrapper, merged, hostname)
            merged["health"] = wrapper["health"]
            projects.append(merged)
        data["projects"] = projects
        _write_data(data)

    return merged


def read_data() -> dict:
    return _read_data()


def reconcile_with_registry() -> list[dict]:
    """Cross-reference data.json with projects.yml, removing orphan entries.

    Returns the reconciled project list (also updates data.json on disk).
    """
    entries = load_registry()
    registry_slugs = {e.slug for e in entries if e.slug}
    registry_names = {e.name for e in entries}
    registry_paths = {normalize_path(e.path) for e in entries if e.path}

    data = _read_data()
    projects = data.get("projects", [])

    reconciled = []
    for p in projects:
        p_slug = p.get("slug", "")
        p_name = p.get("name", "")
        p_path = normalize_path(p.get("path", ""))
        # Keep if slug, name, or path matches something in registry
        if (p_slug and p_slug in registry_slugs) or p_name in registry_names or p_path in registry_paths:
            reconciled.append(p)

    if len(reconciled) != len(projects):
        data["projects"] = reconciled
        with file_lock(LOCK_FILE):
            _write_data(data)

    return reconciled
