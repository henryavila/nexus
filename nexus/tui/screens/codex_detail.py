from __future__ import annotations

from typing import Any

try:
    from textual.binding import Binding
    from textual.app import ComposeResult
    from textual.containers import Vertical
    from textual.screen import ModalScreen
    from textual.widgets import Footer, Static
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

    class Footer(_TextualStub):
        pass

    class Static(_TextualStub):
        pass

from rich.markdown import Markdown as RichMarkdown

from nexus.codex_reader import (
    extract_images,
    extract_markdown_sections,
    format_section_label,
    replace_images_with_placeholders,
    slice_markdown_from_section,
)
from nexus.tui.screens.codex_section_picker import CodexSectionPickerScreen


class CodexDetailScreen(ModalScreen[None]):
    """Dedicated Codex reader with section navigation."""

    BINDINGS = [
        Binding("escape", "dismiss_screen", "Fechar"),
        Binding("q", "dismiss_screen", "Fechar"),
        Binding("e", "edit_codex", "Editar"),
        Binding("g", "open_sections", "Ir para seção"),
        Binding("s", "open_sections", "Ir para seção", show=False),
        Binding("v", "view_images", "Ver imagens"),
    ]

    DEFAULT_CSS = """
    CodexDetailScreen {
        layout: vertical;
    }
    #codex-reader {
        width: auto;
        height: 1fr;
        margin: 1 2 0 2;
        border: thick $accent;
        background: $surface;
    }
    #codex-reader-scroll {
        height: 1fr;
        padding: 1 2 0 2;
        overflow-y: auto;
    }
    #codex-reader .reader-kicker {
        color: $text-muted;
        margin-bottom: 1;
    }
    #codex-reader .detail-title {
        text-style: bold;
        margin-bottom: 1;
    }
    #codex-reader .detail-label {
        color: $text-muted;
        margin-bottom: 1;
    }
    #codex-reader .reader-current {
        margin-top: 1;
        margin-bottom: 1;
    }
    #codex-reader .reader-body {
        border-top: solid $primary-darken-2;
        padding-top: 1;
        padding-bottom: 1;
    }
    """

    def __init__(self, entry: dict, **kwargs):
        super().__init__(**kwargs)
        self.codex_data = entry
        self.sections = extract_markdown_sections(entry.get("content", ""))
        self._section_index: int | None = None

    def _current_content(self) -> str:
        content = self.codex_data.get("content", "")
        if not content.strip():
            return "_Sem conteúdo._\n"
        sliced = slice_markdown_from_section(content, self.sections, self._section_index)
        return replace_images_with_placeholders(sliced)

    def _current_section_label(self) -> str:
        if self._section_index is None:
            return "Topo do documento"
        return format_section_label(self.sections[self._section_index])

    def _meta_parts(self) -> list[str]:
        e = self.codex_data
        parts = [f"Tipo: {e.get('kind', '')}", f"Domínio: {e.get('domain', '')}", f"Slug: {e.get('slug', '')}"]
        if e.get("created"):
            parts.append(f"Criado: {e['created']}")
        if e.get("updated"):
            parts.append(f"Atualizado: {e['updated']}")
        if self.sections:
            parts.append(f"Seções: {len(self.sections)}")
        return parts

    def _refresh_reader(self) -> None:
        try:
            self.query_one("#codex-reader-current", Static).update(
                f"Seção atual: {self._current_section_label()}"
            )
            self.query_one("#codex-reader-body", Static).update(
                RichMarkdown(self._current_content(), code_theme="monokai")
            )
        except Exception:
            pass

    def _set_section_index(self, section_index: int | None) -> None:
        if section_index is not None and (section_index < 0 or section_index >= len(self.sections)):
            return
        self._section_index = section_index
        self._refresh_reader()

    def compose(self) -> ComposeResult:
        e = self.codex_data

        with Vertical(id="codex-reader"):
            with Vertical(id="codex-reader-scroll"):
                yield Static("CODEx Reader", classes="reader-kicker")
                yield Static(
                    f"\U0001F4D6 {e.get('title', '???')}",
                    classes="detail-title",
                )
                yield Static("  |  ".join(self._meta_parts()), classes="detail-label")
                yield Static(
                    f"Seção atual: {self._current_section_label()}",
                    id="codex-reader-current",
                    classes="detail-label reader-current",
                )
                yield Static(
                    RichMarkdown(self._current_content(), code_theme="monokai"),
                    id="codex-reader-body",
                    classes="reader-body",
                )
            yield Footer()

    def action_dismiss_screen(self) -> None:
        self.dismiss(None)

    def action_edit_codex(self) -> None:
        self.dismiss("edit")

    def action_view_images(self) -> None:
        """Open images found in the current section with the system viewer."""
        import subprocess
        from nexus.codex import CODEX_DIR

        content = self.codex_data.get("content", "")
        sliced = slice_markdown_from_section(content, self.sections, self._section_index)
        images = extract_images(sliced)
        if not images:
            self.notify("Nenhuma imagem encontrada nesta seção", severity="warning")
            return

        opened = 0
        for _alt, rel_path in images:
            abs_path = (CODEX_DIR / rel_path).resolve()
            if not abs_path.is_file():
                self.notify(f"Arquivo não encontrado: {rel_path}", severity="warning")
                continue
            try:
                win_path = subprocess.check_output(
                    ["wslpath", "-w", str(abs_path)],
                    stderr=subprocess.DEVNULL,
                ).decode().strip()
                subprocess.Popen(
                    ["explorer.exe", win_path],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                opened += 1
            except FileNotFoundError:
                # Fallback for non-WSL environments
                subprocess.Popen(
                    ["xdg-open", str(abs_path)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                opened += 1
            except Exception:
                self.notify(f"Erro ao abrir: {rel_path}", severity="error")
        if opened:
            self.notify(f"{opened} imagem(ns) aberta(s) no visualizador externo")

    def action_open_sections(self) -> None:
        if not self.sections:
            try:
                self.notify("Documento sem headings mapeáveis", severity="warning")
            except Exception:
                pass
            return
        try:
            self.app.push_screen(
                CodexSectionPickerScreen(self.sections, self._section_index),
                callback=self._set_section_index,
            )
        except Exception:
            pass
