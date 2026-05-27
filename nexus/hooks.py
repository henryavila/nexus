from __future__ import annotations

import json
from pathlib import Path

HOOK_START = "# --- nexus-hook-start ---"
HOOK_END = "# --- nexus-hook-end ---"
HOOK_BLOCK = (
    HOOK_START + "\n"
    "python3 -m nexus scan --project \"$(git rev-parse --show-toplevel)\" 2>/dev/null &\n"
    + HOOK_END + "\n"
)


def _strip_hook_block(text: str) -> str:
    if HOOK_START not in text or HOOK_END not in text:
        return text

    lines = text.splitlines()
    out: list[str] = []
    inside = False
    for ln in lines:
        if ln.strip() == HOOK_START:
            inside = True
            continue
        if ln.strip() == HOOK_END:
            inside = False
            continue
        if not inside:
            out.append(ln)
    out_text = "\n".join(out).rstrip() + "\n"
    return out_text


def _safe_exists(p: Path) -> bool:
    try:
        return p.exists()
    except OSError:
        return False


def install_git_hook(project_path: str) -> bool:
    root = Path(project_path)
    git_dir = root / ".git"
    if not _safe_exists(git_dir):
        return False

    hook_file = git_dir / "hooks" / "post-commit"
    hook_file.parent.mkdir(parents=True, exist_ok=True)
    if hook_file.exists():
        text = hook_file.read_text(encoding="utf-8")
        if HOOK_START in text:
            return False  # already installed
    else:
        text = "#!/usr/bin/env bash\n"

    if not text.endswith("\n"):
        text += "\n"
    new_text = text + "\n" + HOOK_BLOCK

    hook_file.write_text(new_text, encoding="utf-8")
    hook_file.chmod(0o755)
    return True


CLAUDE_HOOK_CMD = 'nexus scan --project "$(git rev-parse --show-toplevel 2>/dev/null || pwd)" 2>/dev/null &'
CLAUDE_HOOK_MATCHER = "Bash|Write|Edit"


def install_claude_hook(project_path: str) -> bool:
    """Install nexus scan hook in .claude/settings.local.json."""
    root = Path(project_path)
    if not _safe_exists(root):
        return False

    settings_file = root / ".claude" / "settings.local.json"
    settings_file.parent.mkdir(parents=True, exist_ok=True)

    if _safe_exists(settings_file):
        try:
            settings = json.loads(settings_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, ValueError):
            settings = {}
    else:
        settings = {}

    # Check if hook already exists
    hooks = settings.get("hooks", {})
    post_tool = hooks.get("PostToolUse", [])
    for entry in post_tool:
        for h in entry.get("hooks", []):
            if "nexus scan" in h.get("command", ""):
                return False  # already installed

    nexus_entry = {
        "matcher": CLAUDE_HOOK_MATCHER,
        "hooks": [
            {"type": "command", "command": CLAUDE_HOOK_CMD}
        ]
    }
    post_tool.append(nexus_entry)
    hooks["PostToolUse"] = post_tool
    settings["hooks"] = hooks

    settings_file.write_text(json.dumps(settings, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return True


def remove_claude_hook(project_path: str) -> bool:
    """Remove nexus scan hook from .claude/settings.local.json."""
    root = Path(project_path)
    settings_file = root / ".claude" / "settings.local.json"
    if not settings_file.exists():
        return False

    try:
        settings = json.loads(settings_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, ValueError):
        return False

    hooks = settings.get("hooks", {})
    post_tool = hooks.get("PostToolUse", [])
    filtered = []
    removed = False
    for entry in post_tool:
        has_nexus = any("nexus scan" in h.get("command", "") for h in entry.get("hooks", []))
        if has_nexus:
            removed = True
        else:
            filtered.append(entry)

    if not removed:
        return False

    if filtered:
        hooks["PostToolUse"] = filtered
    else:
        hooks.pop("PostToolUse", None)

    if hooks:
        settings["hooks"] = hooks
    else:
        settings.pop("hooks", None)

    settings_file.write_text(json.dumps(settings, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return True


def remove_git_hook(project_path: str) -> bool:
    root = Path(project_path)
    git_dir = root / ".git"
    if not git_dir.exists():
        return False

    hook_file = git_dir / "hooks" / "post-commit"
    if not hook_file.exists():
        return False

    text = hook_file.read_text(encoding="utf-8")
    new_text = _strip_hook_block(text)
    if new_text != text:
        hook_file.write_text(new_text, encoding="utf-8")
        hook_file.chmod(0o755)
        return True
    return False
