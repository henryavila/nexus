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


class SkillDetailScreen(ModalScreen[None]):
    """Read-only detail view of a skill."""

    BINDINGS = [
        Binding("escape", "dismiss_screen", "Fechar"),
        Binding("q", "dismiss_screen", "Fechar"),
        Binding("e", "edit_skill", "Editar"),
    ]

    DEFAULT_CSS = """
    SkillDetailScreen {
        align: center middle;
    }
    #skill-detail {
        width: 72;
        max-width: 90%;
        height: auto;
        max-height: 80%;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
        overflow-y: auto;
    }
    #skill-detail .detail-label {
        color: $text-muted;
        margin-top: 1;
    }
    #skill-detail .detail-value {
        padding: 0 1;
    }
    #skill-detail .detail-title {
        text-style: bold;
        margin-bottom: 1;
    }
    #skill-detail .detail-footer {
        color: $text-muted;
        margin-top: 1;
        text-align: center;
    }
    """

    def __init__(self, skill: dict, **kwargs):
        super().__init__(**kwargs)
        self.skill_data = skill

    def compose(self) -> ComposeResult:
        s = self.skill_data
        presence = s.get("presence", {})
        if not presence:
            badge = "❓"
        elif any(v.get("global") for v in presence.values()):
            badge = "\U0001F310"
        else:
            badge = "\U0001F4E6"

        with Vertical(id="skill-detail"):
            yield Static(
                f"{badge} {s.get('title', s.get('slug', '???'))}",
                classes="detail-title",
            )
            yield Static(
                f"Slug: {s.get('slug', '')}",
                classes="detail-label",
            )

            url = s.get("url", "")
            if url:
                yield Static("URL:", classes="detail-label")
                yield Static(url, classes="detail-value")

            yield Static("Presença:", classes="detail-label")
            if presence:
                for hostname, info in presence.items():
                    if info.get("global"):
                        yield Static(f"  \U0001F5A5️ {hostname} — global", classes="detail-value")
                    else:
                        repos = ", ".join(info.get("repos", []))
                        yield Static(f"  \U0001F5A5️ {hostname} — {repos}", classes="detail-value")
            else:
                yield Static("  Nenhum environment detectado — execute 'nexus scan'", classes="detail-value")

            yield Static("[e] Editar  [esc] Fechar", classes="detail-footer")

    def action_dismiss_screen(self) -> None:
        self.dismiss(None)

    def action_edit_skill(self) -> None:
        self.dismiss("edit")
