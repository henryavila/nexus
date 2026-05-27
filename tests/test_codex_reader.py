from nexus.codex_reader import (
    CodexSection,
    extract_images,
    extract_markdown_sections,
    format_section_label,
    replace_images_with_placeholders,
    slice_markdown_from_section,
)
from nexus.tui import CodexDetailScreen, CodexSectionPickerScreen, Footer


def test_extract_markdown_sections_preserves_heading_hierarchy():
    content = "# Guia\n\n## Parser\n\n### Edge Cases\n\n#### Casos Raros\n"

    sections = extract_markdown_sections(content)

    assert [(section.level, section.title) for section in sections] == [
        (1, "Guia"),
        (2, "Parser"),
        (3, "Edge Cases"),
        (4, "Casos Raros"),
    ]


def test_extract_markdown_sections_ignores_fenced_code_blocks():
    content = (
        "# Guia\n\n"
        "```md\n"
        "## Nao e secao\n"
        "### Tambem nao\n"
        "```\n\n"
        "## Secao real\n"
    )

    sections = extract_markdown_sections(content)

    assert [(section.level, section.title) for section in sections] == [
        (1, "Guia"),
        (2, "Secao real"),
    ]


def test_format_section_label_keeps_visual_heading_level():
    section = CodexSection(level=3, title="Navegacao", line_index=12)

    assert format_section_label(section) == "    ### Navegacao"


def test_slice_markdown_from_section_returns_document_from_selected_heading():
    content = (
        "# Guia\n"
        "intro\n\n"
        "## Parser\n"
        "parser body\n\n"
        "### Edge Cases\n"
        "edge body\n"
    )
    sections = extract_markdown_sections(content)

    sliced = slice_markdown_from_section(content, sections, 1)

    assert sliced.startswith("## Parser")
    assert "# Guia" not in sliced
    assert "### Edge Cases" in sliced


def test_slice_markdown_from_section_none_returns_full_document():
    content = "# Guia\n\n## Parser\n"
    sections = extract_markdown_sections(content)

    assert slice_markdown_from_section(content, sections, None) == content


def test_codex_detail_screen_builds_sections_for_reader_popup():
    screen = CodexDetailScreen({
        "title": "Guia",
        "slug": "guia",
        "content": "# Guia\n\n## Parser\n\n### Edge Cases\n",
    })

    assert [format_section_label(section) for section in screen.sections] == [
        "# Guia",
        "  ## Parser",
        "    ### Edge Cases",
    ]


def test_codex_detail_screen_changes_visible_document_when_section_changes():
    screen = CodexDetailScreen({
        "title": "Guia",
        "slug": "guia",
        "content": "# Guia\nintro\n\n## Parser\nbody\n",
    })

    screen._set_section_index(1)

    assert screen._section_index == 1
    assert screen._current_content().startswith("## Parser")
    assert "# Guia" not in screen._current_content()


def test_extract_images_finds_all_image_references():
    content = "# Title\n![Foto](./assets/img.jpg)\ntext\n![Logo](logo.png)\n"
    images = extract_images(content)
    assert images == [("Foto", "./assets/img.jpg"), ("Logo", "logo.png")]


def test_extract_images_returns_empty_for_no_images():
    assert extract_images("# No images\nJust text.\n") == []


def test_replace_images_with_placeholders_substitutes_syntax():
    content = "Before\n![Foto](img.jpg)\nAfter"
    result = replace_images_with_placeholders(content)
    assert "![" not in result
    assert "🖼" in result
    assert "Foto" in result
    assert "`v`" in result


def test_codex_detail_screen_content_replaces_images():
    screen = CodexDetailScreen({
        "title": "T",
        "slug": "t",
        "content": "# T\n![Imagem](./assets/x.jpeg)\n",
    })
    rendered = screen._current_content()
    assert "![" not in rendered
    assert "🖼" in rendered


def test_codex_detail_screen_uses_g_as_visible_section_binding():
    screen = CodexDetailScreen({
        "title": "Guia",
        "slug": "guia",
        "content": "# Guia\n\n## Parser\n",
    })

    bindings = {binding.key: binding for binding in screen.BINDINGS}

    assert bindings["g"].show is True
    assert bindings["s"].show is False


def test_codex_detail_screen_renders_textual_footer_for_visible_shortcuts():
    import asyncio
    from textual.app import App as BaseApp, ComposeResult
    from textual.widgets import Static

    codex_data = {
        "title": "Guia",
        "slug": "guia",
        "content": "# Guia\n\n## Parser\n",
    }
    found_footer = []
    found_codex_footer_id = []

    class HostApp(BaseApp):
        def compose(self) -> ComposeResult:
            yield Static("host")

        def on_mount(self) -> None:
            self.push_screen(CodexDetailScreen(codex_data))

    async def run_check():
        async with HostApp().run_test() as pilot:
            await pilot.pause()
            active = pilot.app.screen
            footer_widgets = active.query("Footer")
            found_footer.append(len(footer_widgets) > 0)
            codex_footer = [w for w in active.query("*") if getattr(w, "id", None) == "codex-reader-footer"]
            found_codex_footer_id.append(len(codex_footer) > 0)

    asyncio.run(run_check())
    assert found_footer[0], "Expected Footer widget in CodexDetailScreen"
    assert not found_codex_footer_id[0], "codex-reader-footer should not be present"


def test_codex_section_picker_includes_document_top_option():
    picker = CodexSectionPickerScreen([
        CodexSection(level=1, title="Guia", line_index=0),
        CodexSection(level=2, title="Parser", line_index=2),
    ])

    assert picker.option_labels == [
        "Topo do documento",
        "# Guia",
        "  ## Parser",
    ]
