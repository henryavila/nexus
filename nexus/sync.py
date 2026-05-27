from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _has_remote(repo_path: str) -> bool:
    """Check if the repo has a remote configured."""
    remote = subprocess.run(
        ["git", "remote"],
        cwd=repo_path, capture_output=True, text=True,
    )
    return remote.returncode == 0 and bool(remote.stdout.strip())


def _warn_sync_failure(message: str) -> None:
    """Print a sync failure warning to stderr."""
    print(f"⚠ nexus sync: {message}", file=sys.stderr)


def pull_rebase(repo_path: str) -> tuple[bool, str]:
    """Pull --rebase a git repo. Returns (success, message).

    If no remote exists, returns (True, skip message) — not an error.
    If pull fails (conflict/timeout), aborts rebase and returns (False, error).
    """
    if not _has_remote(repo_path):
        return True, "sem remote configurado, pulando sync."

    try:
        pull = subprocess.run(
            ["git", "pull", "--rebase", "--autostash"],
            cwd=repo_path, capture_output=True, text=True,
            timeout=15,
        )
    except subprocess.TimeoutExpired:
        subprocess.run(
            ["git", "rebase", "--abort"],
            cwd=repo_path, capture_output=True, text=True,
        )
        return False, "pull --rebase timeout (rede indisponível?)"
    if pull.returncode == 0:
        return True, pull.stdout.strip() or "Up to date."

    # Pull failed — abort any pending rebase
    subprocess.run(
        ["git", "rebase", "--abort"],
        cwd=repo_path, capture_output=True, text=True,
    )
    return False, pull.stderr.strip() or "pull --rebase falhou"


def _pull_merge(repo_path: str) -> tuple[bool, str]:
    """Fallback: pull with merge when rebase fails. More tolerant with
    divergent YAML changes."""
    try:
        pull = subprocess.run(
            ["git", "pull", "--no-rebase"],
            cwd=repo_path, capture_output=True, text=True,
            timeout=15,
        )
    except subprocess.TimeoutExpired:
        return False, "pull --no-rebase timeout (rede indisponível?)"
    if pull.returncode == 0:
        return True, pull.stdout.strip() or "Merged."
    return False, pull.stderr.strip() or "pull --no-rebase falhou"


def _commit_and_push(repo_path: str, files: list[str], command: str) -> bool:
    """Stage specific files, commit, and push.

    Strategy: commit → push → retry(rebase → push) → fallback(merge → push).
    Returns True on success (or no changes), False on failure.
    """
    try:
        # Verify repo path exists
        if not Path(repo_path).is_dir():
            _warn_sync_failure(f"erro inesperado ao sincronizar ({command}).")
            return False

        # Expand glob patterns (e.g. "data/skills/*.md") to actual files
        expanded = []
        for f in files:
            if "*" in f:
                expanded.extend(
                    str(p.relative_to(repo_path))
                    for p in Path(repo_path).glob(f)
                )
            elif (Path(repo_path) / f).exists():
                expanded.append(f)
        files = expanded
        if not files:
            return True

        # Check if specified files have changes
        status = subprocess.run(
            ["git", "status", "--porcelain", "--"] + files,
            cwd=repo_path, capture_output=True, text=True,
        )
        if status.returncode != 0 or not status.stdout.strip():
            return True

        # Stage only specified files
        subprocess.run(
            ["git", "add", "--"] + files,
            cwd=repo_path, capture_output=True, text=True,
        )

        # Verify something is actually staged
        diff = subprocess.run(
            ["git", "diff", "--cached", "--quiet"],
            cwd=repo_path, capture_output=True,
        )
        if diff.returncode == 0:
            return True

        # Commit
        subprocess.run(
            ["git", "commit", "-m", f"[nexus-auto] {command} sync"],
            cwd=repo_path, capture_output=True, text=True,
        )

        # Push if remote exists
        if not _has_remote(repo_path):
            return True

        push = subprocess.run(
            ["git", "push"],
            cwd=repo_path, capture_output=True, text=True,
            timeout=15,
        )
        if push.returncode == 0:
            return True

        # Retry 1: rebase
        ok, _ = pull_rebase(repo_path)
        if ok:
            push = subprocess.run(
                ["git", "push"],
                cwd=repo_path, capture_output=True, text=True,
                timeout=15,
            )
            if push.returncode == 0:
                return True

        # Retry 2: merge fallback
        ok, _ = _pull_merge(repo_path)
        if ok:
            push = subprocess.run(
                ["git", "push"],
                cwd=repo_path, capture_output=True, text=True,
                timeout=15,
            )
            if push.returncode == 0:
                return True

        _warn_sync_failure(
            f"não foi possível sincronizar ({command}). "
            "Execute 'git status' no diretório do nexus."
        )
        return False
    except Exception:
        _warn_sync_failure(f"erro inesperado ao sincronizar ({command}).")
        return False


def quick_sync(repo_path: str, files: list[str], command: str) -> bool:
    """Sync specific files only — lightweight alternative to auto_sync_registry.

    Use for single-resource mutations (codex edit, idea add, etc).
    """
    return _commit_and_push(repo_path, files, command)


def auto_sync_registry(repo_path: str, command: str) -> bool:
    """Stage ALL data files, commit, and push. Use for scan or bulk operations.

    Strategy: commit → push → retry(rebase → push) → fallback(merge → push).
    Prints warning to stderr on failure — never raises.
    Returns True on success (or no changes), False on push failure.
    """
    data_files = [
        "data/projects.yml",
        "data/ideas.yml",
        "data/apps.yml",
        "data/environments.yml",
    ]
    # Include codex dir if it exists (may not on fresh repos)
    codex_dir = Path(repo_path) / "data" / "codex"
    if codex_dir.exists():
        data_files.append("data/codex/")
    # Include skills/*.md if dir exists
    skills_dir = Path(repo_path) / "data" / "skills"
    if skills_dir.exists():
        for md in skills_dir.glob("*.md"):
            data_files.append(f"data/skills/{md.name}")

    return _commit_and_push(repo_path, data_files, command)
