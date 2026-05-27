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


class IdeaDetailScreen(ModalScreen[None]):
    """Read-only detail view of an idea."""

    BINDINGS = [
        Binding("escape", "dismiss_screen", "Fechar"),
        Binding("q", "dismiss_screen", "Fechar"),
        Binding("e", "edit_idea", "Editar"),
    ]

    DEFAULT_CSS = """
    IdeaDetailScreen {
        align: center middle;
    }
    #idea-detail {
        width: 72;
        max-width: 90%;
        height: auto;
        max-height: 80%;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
        overflow-y: auto;
    }
    #idea-detail .detail-label {
        color: $text-muted;
        margin-top: 1;
    }
    #idea-detail .detail-value {
        padding: 0 1;
    }
    #idea-detail .detail-title {
        text-style: bold;
        margin-bottom: 1;
    }
    #idea-detail .detail-footer {
        color: $text-muted;
        margin-top: 1;
        text-align: center;
    }
    """

    def __init__(self, idea: dict, **kwargs):
        super().__init__(**kwargs)
        self.idea_data = idea

    def compose(self) -> ComposeResult:
        idea = self.idea_data
        priority_badge = {
            "high": "\U0001F534", "medium": "\U0001F7E1", "low": "\U0001F7E2",
        }.get(idea.get("priority", "medium"), "\U0001F7E1")

        with Vertical(id="idea-detail"):
            yield Static(
                f"{priority_badge} {idea.get('title', '???')}",
                classes="detail-title",
            )
            yield Static(
                f"Prioridade: {idea.get('priority', 'medium')}  |  "
                f"Domínio: {idea.get('domain', '')}  |  "
                f"ID: {idea.get('id', '')}",
                classes="detail-label",
            )

            desc = idea.get("description", "")
            if desc:
                yield Static("Descrição:", classes="detail-label")
                yield Static(desc, classes="detail-value")

            refs = idea.get("references") or []
            if refs:
                yield Static("Referências:", classes="detail-label")
                yield Static("\n".join(refs), classes="detail-value")

            notes = idea.get("notes") or ""
            if notes:
                yield Static("Notas:", classes="detail-label")
                yield Static(notes, classes="detail-value")

            created = idea.get("created", "")
            if created:
                yield Static(f"Criada em: {created}", classes="detail-label")

            yield Static("[e] Editar  [esc] Fechar", classes="detail-footer")

    def action_dismiss_screen(self) -> None:
        self.dismiss(None)

    def action_edit_idea(self) -> None:
        self.dismiss("edit")
