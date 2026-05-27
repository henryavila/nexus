"""Environment (machine/device) management for Nexus."""

from __future__ import annotations

import socket
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import yaml

from . import ENVIRONMENTS_YML


@dataclass
class EnvironmentEntry:
    hostname: str
    name: str
    location: str
    last_seen: str = ""
    paths: dict[str, str] = field(default_factory=dict)
    absent: list[str] = field(default_factory=list)


def load_environments() -> list[EnvironmentEntry]:
    if not ENVIRONMENTS_YML.exists():
        return []
    with open(ENVIRONMENTS_YML, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not data or "environments" not in data:
        return []
    entries = []
    for item in data["environments"]:
        if not isinstance(item, dict) or "hostname" not in item:
            continue
        entries.append(
            EnvironmentEntry(
                hostname=item["hostname"],
                name=item.get("name", item["hostname"]),
                location=item.get("location", ""),
                last_seen=str(item.get("last_seen", "")),
                paths=item.get("paths") or {},
                absent=item.get("absent") or [],
            )
        )
    return entries


def save_environments(entries: list[EnvironmentEntry]) -> None:
    data = []
    for e in entries:
        d: dict = {
            "hostname": e.hostname,
            "name": e.name,
            "location": e.location,
        }
        if e.last_seen:
            d["last_seen"] = e.last_seen
        if e.paths:
            d["paths"] = e.paths
        if e.absent:
            d["absent"] = e.absent
        data.append(d)
    ENVIRONMENTS_YML.parent.mkdir(parents=True, exist_ok=True)
    with open(ENVIRONMENTS_YML, "w", encoding="utf-8") as f:
        yaml.dump(
            {"environments": data},
            f,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        )


def get_current_hostname() -> str:
    return socket.gethostname()


def find_environment(hostname: str | None = None) -> EnvironmentEntry | None:
    hostname = hostname or get_current_hostname()
    for e in load_environments():
        if e.hostname == hostname:
            return e
    return None


def get_environment_path(slug: str, hostname: str | None = None) -> str | None:
    env = find_environment(hostname)
    if env is None:
        return None
    return env.paths.get(slug)


def update_last_seen(hostname: str | None = None) -> None:
    hostname = hostname or get_current_hostname()
    today = date.today().isoformat()
    entries = load_environments()
    for e in entries:
        if e.hostname == hostname:
            if e.last_seen == today:
                return  # Avoid spurious writes/commits
            e.last_seen = today
            save_environments(entries)
            return


def register_environment(name: str, location: str, hostname: str | None = None) -> EnvironmentEntry:
    hostname = hostname or get_current_hostname()
    existing = find_environment(hostname)
    if existing:
        return existing
    entry = EnvironmentEntry(
        hostname=hostname,
        name=name,
        location=location,
        last_seen=date.today().isoformat(),
    )
    entries = load_environments()
    entries.append(entry)
    save_environments(entries)
    return entry


def register_environment_non_interactive(hostname: str | None = None) -> EnvironmentEntry:
    hostname = hostname or get_current_hostname()
    return register_environment(hostname, "unknown", hostname)


def set_environment_path(hostname: str, slug: str, path: str) -> None:
    entries = load_environments()
    for e in entries:
        if e.hostname == hostname:
            e.paths[slug] = path
            if slug in e.absent:
                e.absent.remove(slug)
            save_environments(entries)
            return


def resolve_path_for_entry(slug: str, entry_path: str | None = None) -> str | None:
    """Resolve local path for a project/app on the current machine.
    Priority: environment paths > entry.path > None"""
    env = find_environment()
    if env and slug:
        env_path = env.paths.get(slug)
        if env_path:
            return env_path
    return entry_path


def update_environment(hostname: str, name: str | None = None, location: str | None = None) -> bool:
    """Update an environment's name and/or location. Returns True if found and updated."""
    entries = load_environments()
    for e in entries:
        if e.hostname == hostname:
            if name is not None:
                e.name = name
            if location is not None:
                e.location = location
            save_environments(entries)
            return True
    return False


def mark_absent(hostname: str, slug: str) -> None:
    entries = load_environments()
    for e in entries:
        if e.hostname == hostname:
            if slug not in e.absent:
                e.absent.append(slug)
            if slug in e.paths:
                del e.paths[slug]
            save_environments(entries)
            return


def migrate_paths_from_registry(name: str, location: str) -> EnvironmentEntry:
    """One-time migration: reads paths from projects.yml and creates environment entry."""
    from nexus.registry import load_registry
    hostname = get_current_hostname()
    env = find_environment(hostname)
    if env is not None:
        return env  # Already migrated

    entries = load_registry()
    paths = {}
    for e in entries:
        if e.path and e.slug:
            paths[e.slug] = e.path

    env = EnvironmentEntry(
        hostname=hostname,
        name=name,
        location=location,
        last_seen=date.today().isoformat(),
        paths=paths,
    )
    all_envs = load_environments()
    all_envs.append(env)
    save_environments(all_envs)
    return env
