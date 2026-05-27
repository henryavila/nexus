from __future__ import annotations

from typing import Any

try:
    from textual.binding import Binding
    from textual.app import ComposeResult
    from textual.containers import Vertical
    from textual.screen import ModalScreen
    from textual.widgets import Input, Static
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

    class Input(_TextualStub):
        class Changed:
            input = None
            value = ""

        class Submitted:
            input = None

    class Static(_TextualStub):
        pass


class CodexOrderScreen(ModalScreen[int | None]):
    """Small modal to set codex entry order inline."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancelar"),
    ]

    DEFAULT_CSS = """
    CodexOrderScreen {
        align: center middle;
    }
    #codex-order-box {
        width: 40;
        height: auto;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }
    #codex-order-box .detail-title {
        text-style: bold;
        margin-bottom: 1;
    }
    #codex-order-box .detail-label {
        color: $text-muted;
        margin-bottom: 1;
    }
    """

    def __init__(self, current_order: int | None = None, **kwargs):
        super().__init__(**kwargs)
        self.current_order = current_order

    def compose(self) -> ComposeResult:
        with Vertical(id="codex-order-box"):
            yield Static("Definir ordem", classes="detail-title")
            yield Static("Vazio = sem ordem · Esc = cancelar", classes="detail-label")
            yield Input(
                value=str(self.current_order) if self.current_order is not None else "",
                placeholder="Ex: 1, 2, 3...",
                type="integer",
                id="codex-order-input",
            )

    def on_mount(self) -> None:
        try:
            self.query_one("#codex-order-input", Input).focus()
        except Exception:
            pass

    def on_input_submitted(self, event: Input.Submitted) -> None:
        raw = event.value.strip()
        if raw == "":
            self.dismiss(None)
            return
        try:
            self.dismiss(int(raw))
        except ValueError:
            self.notify("Valor inválido — use um número inteiro", severity="warning")

    def action_cancel(self) -> None:
        self.dismiss(self.current_order)
