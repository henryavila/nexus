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

from nexus.codex_reader import format_section_label


class CodexSectionPickerScreen(ModalScreen[int | None]):
    """Popup with hierarchical heading navigation for Codex."""

    BINDINGS = [
        Binding("escape", "dismiss_screen", "Fechar"),
        Binding("q", "dismiss_screen", "Fechar"),
    ]

    DEFAULT_CSS = """
    CodexSectionPickerScreen {
        align: center middle;
    }
    #codex-sections {
        width: 72;
        max-width: 90%;
        height: auto;
        max-height: 80%;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }
    #codex-sections .detail-title {
        text-style: bold;
        margin-bottom: 1;
    }
    #codex-sections .detail-label {
        color: $text-muted;
        margin-bottom: 1;
    }
    #codex-sections OptionList {
        height: auto;
        max-height: 18;
    }
    """

    def __init__(self, sections, current_index: int | None = None, **kwargs):
        super().__init__(**kwargs)
        self.sections = sections
        self.current_index = current_index
        self.option_labels = ["Topo do documento"] + [format_section_label(section) for section in sections]

    def compose(self) -> ComposeResult:
        with Vertical(id="codex-sections"):
            yield Static("Seções do documento", classes="detail-title")
            yield Static("Enter para navegar, Esc para fechar", classes="detail-label")
            yield OptionList(*self.option_labels)

    def on_mount(self) -> None:
        try:
            option_list = self.query_one(OptionList)
            option_list.highlighted = 0 if self.current_index is None else self.current_index + 1
        except Exception:
            pass

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option_index == 0:
            self.dismiss(None)
            return
        self.dismiss(event.option_index - 1)

    def action_dismiss_screen(self) -> None:
        self.dismiss(self.current_index)
