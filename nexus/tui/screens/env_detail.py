from __future__ import annotations

from typing import Any

try:
    from textual.binding import Binding
    from textual.app import ComposeResult
    from textual.containers import Vertical
    from textual.screen import ModalScreen
    from textual.widgets import Static
except ModuleNotFoundError:
    ComposeResult = Any

    class Binding:
        def __init__(self, key: str, action: str, description: str = "",
                     show: bool = True, priority: bool = False):
            self.key = key
            self.action = action
            self.description = description
            self.show = show
            self.priority = priority

    class _TextualStub:
        def __init__(self, *args, **kwargs):
            self.renderable = args[0] if args else None

        @classmethod
        def __class_getitem__(cls, _item):
            return cls

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    class ModalScreen(_TextualStub):
        BINDINGS = []

        def dismiss(self, result=None):
            return result

    class Vertical(_TextualStub):
        pass

    class Static(_TextualStub):
        pass


class EnvDetailScreen(ModalScreen[None]):
    """Read-only detail view of an environment."""

    BINDINGS = [
        Binding("escape", "dismiss_screen", "Fechar"),
        Binding("q", "dismiss_screen", "Fechar"),
    ]

    DEFAULT_CSS = """
    EnvDetailScreen {
        align: center middle;
    }
    #env-detail {
        width: 72;
        max-width: 90%;
        height: auto;
        max-height: 80%;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
        overflow-y: auto;
    }
    #env-detail .detail-label {
        color: $text-muted;
        margin-top: 1;
    }
    #env-detail .detail-value {
        padding: 0 1;
    }
    #env-detail .detail-title {
        text-style: bold;
        margin-bottom: 1;
    }
    #env-detail .detail-footer {
        color: $text-muted;
        margin-top: 1;
        text-align: center;
    }
    """

    def __init__(self, env: dict, skills_data: dict | None = None, **kwargs):
        super().__init__(**kwargs)
        self.env_data = env
        self.skills_data = skills_data or {}

    def compose(self) -> ComposeResult:
        e = self.env_data
        name = e.get("name", e.get("hostname", "???"))
        hostname = e.get("hostname", "???")
        location = e.get("location", "???")
        last_seen = e.get("last_seen", "n/a")

        with Vertical(id="env-detail"):
            yield Static(
                f"\U0001F5A5️ {name}",
                classes="detail-title",
            )
            yield Static(
                f"Hostname: {hostname}  |  Localização: {location}",
                classes="detail-label",
            )

            if last_seen and last_seen != "n/a":
                yield Static("Último acesso:", classes="detail-label")
                yield Static(last_seen, classes="detail-value")

            paths = e.get("paths") or {}
            if paths:
                yield Static(f"Projetos ({len(paths)}):", classes="detail-label")
                for slug, path in sorted(paths.items()):
                    yield Static(f"  {slug}: {path}", classes="detail-value")

            absent = e.get("absent") or []
            if absent:
                yield Static("Ausentes:", classes="detail-label")
                yield Static(", ".join(absent), classes="detail-value")

            # Skills installed on this environment
            hostname = e.get("hostname", "")
            global_skills = []
            repo_skills = []
            for slug, info in self.skills_data.items():
                host_info = info.get("presence", {}).get(hostname)
                if not host_info:
                    continue
                title = info.get("title", slug)
                if host_info.get("global"):
                    global_skills.append(title)
                else:
                    repos = ", ".join(host_info.get("repos", []))
                    repo_skills.append(f"{title} ({repos})")
            if global_skills or repo_skills:
                yield Static("Skills:", classes="detail-label")
                if global_skills:
                    yield Static(f"  \U0001F310 {', '.join(sorted(global_skills))}", classes="detail-value")
                if repo_skills:
                    yield Static(f"  \U0001F4E6 {', '.join(sorted(repo_skills))}", classes="detail-value")

            yield Static("[esc] Fechar", classes="detail-footer")

    def action_dismiss_screen(self) -> None:
        self.dismiss(None)
