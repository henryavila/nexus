"""Auto-discover projects that moved to a new location."""
from __future__ import annotations

from pathlib import Path

from . import EXCLUDED_DIRS


def _search_for_basename(search_root: Path, basename: str, max_depth: int = 2) -> list[Path]:
    """Recursively search for directories named `basename` under `search_root`."""
    results = []
    basename_lower = basename.lower()

    def _walk(directory: Path, depth: int) -> None:
        if depth > max_depth:
            return
        try:
            children = sorted(directory.iterdir())
        except (PermissionError, OSError):
            return
        for child in children:
            try:
                is_dir = child.is_dir()
            except (PermissionError, OSError):
                continue
            if not is_dir:
                continue
            if child.name in EXCLUDED_DIRS or child.name.startswith("."):
                continue
            if child.name.lower() == basename_lower:
                results.append(child)
            else:
                _walk(child, depth + 1)

    _walk(search_root, 0)
    return results


def _safe_exists(p: Path) -> bool:
    try:
        return p.exists()
    except OSError:
        return False


def _score_candidate(candidate: Path) -> int:
    """Higher score = more confident match. Used for sorting."""
    score = 0
    if _safe_exists(candidate / "nexus.yaml"):
        score += 10
    if _safe_exists(candidate / ".git"):
        score += 5
    if _safe_exists(candidate / "CLAUDE.md"):
        score += 3
    if _safe_exists(candidate / "package.json") or _safe_exists(candidate / "pyproject.toml"):
        score += 2
    return score


def find_moved_project(old_path: str, max_levels: int = 3) -> list[str]:
    """Search ancestor directories for a project that moved.

    Walks up to `max_levels` ancestors from the old path, searching each
    for directories matching the project basename.

    Returns a list of candidate paths, sorted by confidence (best first).
    """
    old = Path(old_path)
    basename = old.name
    candidates: list[Path] = []
    seen: set[str] = set()

    # Walk up through ancestor directories
    ancestor = old.parent
    for _ in range(max_levels):
        if not _safe_exists(ancestor):
            ancestor = ancestor.parent
            continue
        for hit in _search_for_basename(ancestor, basename):
            norm = str(hit)
            if norm not in seen:
                seen.add(norm)
                candidates.append(hit)
        next_ancestor = ancestor.parent
        if next_ancestor == ancestor:
            break  # reached filesystem root
        ancestor = next_ancestor

    # Exclude the original path itself (it's not a "new" location)
    old_str = str(old)
    old_resolved = str(old.resolve()) if _safe_exists(old) else old_str
    candidates = [c for c in candidates if str(c) != old_str and str(c) != old_resolved]

    # Sort by confidence score (highest first)
    candidates.sort(key=lambda c: _score_candidate(c), reverse=True)
    return [str(c) for c in candidates]
