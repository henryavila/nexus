"""Cross-registry integrity checks for Nexus."""

from __future__ import annotations

import logging

from nexus import PROJECTS_YML, APPS_YML

logger = logging.getLogger(__name__)


def slug_exists(slug: str) -> str | None:
    from nexus.registry import load_registry
    from nexus.apps import load_apps

    for entry in load_registry():
        if entry.slug == slug:
            return "project"
    for entry in load_apps():
        if entry.slug == slug:
            return "app"
    return None


def check_registry_integrity() -> None:
    from nexus.registry import load_registry, save_registry
    from nexus.apps import load_apps

    app_slugs = {a.slug for a in load_apps()}
    if not app_slugs:
        return

    projects = load_registry()
    dupes = [p for p in projects if p.slug in app_slugs]
    if not dupes:
        return

    cleaned = [p for p in projects if p.slug not in app_slugs]
    for d in dupes:
        logger.warning(
            "Slug '%s' found in both registries. App wins, removing from projects.",
            d.slug,
        )
    save_registry(cleaned)
