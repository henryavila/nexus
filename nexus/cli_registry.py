from __future__ import annotations

import shutil
from typing import NamedTuple


class CliEntry(NamedTuple):
    name: str
    cmd: str
    label: str


CLI_REGISTRY: list[CliEntry] = [
    CliEntry("claude", "claude", "Claude Code"),
    CliEntry("codex", "codex", "Codex CLI"),
    CliEntry("opencode", "opencode", "OpenCode"),
]


def detect_clis() -> list[CliEntry]:
    """Return CLI entries for executables found in PATH."""
    return [cli for cli in CLI_REGISTRY if shutil.which(cli.cmd)]
