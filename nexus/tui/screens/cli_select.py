from __future__ import annotations

from typing import Any

try:
    from textual.binding import Binding
    from textual.app import ComposeResult
    from textual.containers import Vertical
    from textual.screen import ModalScreen
    from textual.widgets import OptionList, Static
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

    class OptionList(_TextualStub):
        class OptionSelected:
            option_index = 0

    class Static(_TextualStub):
        pass

from nexus.cli_registry import CliEntry


class CliSelectScreen(ModalScreen[CliEntry | None]):
    """Modal for selecting which AI CLI to launch."""

    BINDINGS = [Binding("escape", "cancel", "Cancelar")]

    DEFAULT_CSS = """
    CliSelectScreen {
        align: center middle;
    }
    #cli-dialog {
        width: 40;
        height: auto;
        max-height: 16;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }
    #cli-dialog Static {
        width: 100%;
        content-align: center middle;
        margin-bottom: 1;
    }
    #cli-dialog OptionList {
        height: auto;
        max-height: 10;
    }
    """

    def __init__(self, clis: list[CliEntry], **kwargs):
        super().__init__(**kwargs)
        self.clis = clis

    def compose(self) -> ComposeResult:
        with Vertical(id="cli-dialog"):
            yield Static("Selecione o CLI")
            yield OptionList(*[cli.label for cli in self.clis])

    def on_mount(self) -> None:
        self.query_one(OptionList).highlighted = 0

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(self.clis[event.option_index])

    def action_cancel(self) -> None:
        self.dismiss(None)
