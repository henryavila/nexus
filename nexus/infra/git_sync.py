from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def has_remote(repo_path: str) -> bool:
    remote = subprocess.run(
        ["git", "remote"],
        cwd=repo_path, capture_output=True, text=True,
    )
    return remote.returncode == 0 and bool(remote.stdout.strip())


def pull_rebase(repo_path: str) -> tuple[bool, str]:
    if not has_remote(repo_path):
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
    subprocess.run(
        ["git", "rebase", "--abort"],
        cwd=repo_path, capture_output=True, text=True,
    )
    return False, pull.stderr.strip() or "pull --rebase falhou"


def pull_merge(repo_path: str) -> tuple[bool, str]:
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


def commit_and_push(repo_path: str, files: list[str], command: str) -> bool:
    try:
        if not Path(repo_path).is_dir():
            return False
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
        status = subprocess.run(
            ["git", "status", "--porcelain", "--"] + files,
            cwd=repo_path, capture_output=True, text=True,
        )
        if status.returncode != 0 or not status.stdout.strip():
            return True
        subprocess.run(
            ["git", "add", "--"] + files,
            cwd=repo_path, capture_output=True, text=True,
        )
        diff = subprocess.run(
            ["git", "diff", "--cached", "--quiet"],
            cwd=repo_path, capture_output=True,
        )
        if diff.returncode == 0:
            return True
        subprocess.run(
            ["git", "commit", "-m", f"[nexus-auto] {command} sync"],
            cwd=repo_path, capture_output=True, text=True,
        )
        if not has_remote(repo_path):
            return True
        push = subprocess.run(
            ["git", "push"],
            cwd=repo_path, capture_output=True, text=True,
            timeout=15,
        )
        if push.returncode == 0:
            return True
        ok, _ = pull_rebase(repo_path)
        if ok:
            push = subprocess.run(["git", "push"], cwd=repo_path, capture_output=True, text=True, timeout=15)
            if push.returncode == 0:
                return True
        ok, _ = pull_merge(repo_path)
        if ok:
            push = subprocess.run(["git", "push"], cwd=repo_path, capture_output=True, text=True, timeout=15)
            if push.returncode == 0:
                return True
        print(f"⚠ nexus sync: não foi possível sincronizar ({command}).", file=sys.stderr)
        return False
    except Exception:
        print(f"⚠ nexus sync: erro inesperado ao sincronizar ({command}).", file=sys.stderr)
        return False
