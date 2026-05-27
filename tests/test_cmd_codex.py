import argparse
import pytest
from unittest.mock import patch
from nexus.codex import CodexEntry, save_codex_entry, load_codex
from nexus.editors import EditorConfig, save_editors


# CODEX_KINDS sorted: ["anotação", "configuração", "guia", "referência", "tutorial", "workflow"]
# Index 4 = "referência" (1-indexed)


class TestCmdCodexList:
    def test_lists_entries(self, nexus_env, capsys):
        from nexus._legacy_main import cmd_codex_list

        entry = CodexEntry(
            slug="my-guide",
            title="My Guide",
            kind="guia",
            created="2026-01-01",
            updated="2026-01-01",
        )
        save_codex_entry(entry)

        cmd_codex_list(argparse.Namespace())
        out = capsys.readouterr().out
        assert "My Guide" in out
        assert "guia" in out

    def test_empty_list(self, nexus_env, capsys):
        from nexus._legacy_main import cmd_codex_list

        result = cmd_codex_list(argparse.Namespace())
        out = capsys.readouterr().out
        assert "Nenhuma" in out
        assert result == 0


class TestCmdCodexAdd:
    def test_add_happy_path(self, nexus_env, mock_input, mock_editor):
        from nexus._legacy_main import cmd_codex_add

        # _prompt_choice for kind (sorted CODEX_KINDS):
        # 1=anotação, 2=configuração, 3=guia, 4=referência, 5=tutorial, 6=workflow
        # _prompt_choice for domain (sorted DEFAULT_DOMAINS):
        # 1=empreendimentos, 2=estudo, 3=igreja, 4=lazer, 5=pessoal, 6=tech, 7=trabalho
        mock_input.side_effect = [
            "My Codex Entry",  # title
            "4",               # kind choice → "referência"
            "6",               # domain choice → "tech"
            "",                # order (skip)
        ]

        result = cmd_codex_add(argparse.Namespace())
        assert result == 0

        entries = load_codex()
        assert len(entries) == 1
        assert entries[0].title == "My Codex Entry"
        assert entries[0].kind == "referência"
        assert entries[0].domain == "tech"

    def test_add_empty_title_aborts(self, nexus_env, mock_input, capsys):
        from nexus._legacy_main import cmd_codex_add

        mock_input.return_value = ""

        result = cmd_codex_add(argparse.Namespace())
        out = capsys.readouterr().out
        assert result == 1
        assert "obrigatório" in out
        assert load_codex() == []


class TestCmdCodexEdit:
    def test_edit_updates_date(self, nexus_env, mock_editor, capsys):
        from nexus._legacy_main import cmd_codex_edit

        entry = CodexEntry(
            slug="test-entry",
            title="Test Entry",
            kind="guia",
            created="2025-01-01",
            updated="2025-01-01",
            content="Old content",
        )
        save_codex_entry(entry)

        args = argparse.Namespace(query="test-entry", pick=False)
        result = cmd_codex_edit(args)
        assert result == 0

        entries = load_codex()
        assert len(entries) == 1
        # The updated date should be today's date (not the old date)
        assert entries[0].updated != "2025-01-01"

    def test_edit_not_found(self, nexus_env, capsys):
        from nexus._legacy_main import cmd_codex_edit

        args = argparse.Namespace(query="nonexistent", pick=False)
        result = cmd_codex_edit(args)
        out = capsys.readouterr().out
        assert result == 1
        assert "não encontrada" in out

    def test_edit_no_editor(self, nexus_env, capsys):
        from nexus._legacy_main import cmd_codex_edit

        entry = CodexEntry(
            slug="no-editor-entry",
            title="No Editor Entry",
            kind="referência",
            created="2026-01-01",
            updated="2026-01-01",
        )
        save_codex_entry(entry)

        args = argparse.Namespace(query="no-editor-entry", pick=False)
        with patch("nexus._legacy_main.get_default_editor", return_value=None), \
             patch("nexus._legacy_main.editor_add", return_value=None):
            result = cmd_codex_edit(args)

        out = capsys.readouterr().out
        assert result == 1
        assert "Nenhum editor" in out


class TestCmdCodexRemove:
    def test_remove_confirmed(self, nexus_env, mock_input, capsys):
        from nexus._legacy_main import cmd_codex_remove

        entry = CodexEntry(
            slug="to-remove",
            title="To Remove",
            kind="anotação",
            created="2026-01-01",
            updated="2026-01-01",
        )
        save_codex_entry(entry)

        mock_input.return_value = "s"
        args = argparse.Namespace(query="to-remove")
        result = cmd_codex_remove(args)
        assert result == 0
        assert load_codex() == []

    def test_remove_cancelled(self, nexus_env, mock_input, capsys):
        from nexus._legacy_main import cmd_codex_remove

        entry = CodexEntry(
            slug="keep-me",
            title="Keep Me",
            kind="guia",
            created="2026-01-01",
            updated="2026-01-01",
        )
        save_codex_entry(entry)

        mock_input.return_value = "n"
        args = argparse.Namespace(query="keep-me")
        result = cmd_codex_remove(args)
        assert result == 0
        assert len(load_codex()) == 1

    def test_remove_not_found(self, nexus_env, capsys):
        from nexus._legacy_main import cmd_codex_remove

        args = argparse.Namespace(query="nonexistent")
        result = cmd_codex_remove(args)
        out = capsys.readouterr().out
        assert result == 1
        assert "não encontrada" in out


class TestCmdCodexDispatcher:
    def test_no_subcommand(self, nexus_env, capsys):
        from nexus._legacy_main import cmd_codex

        result = cmd_codex(argparse.Namespace())
        assert result == 1


class TestCmdCodexEditorList:
    def test_list_empty(self, nexus_env, capsys):
        from nexus._legacy_main import cmd_codex_editor_list

        result = cmd_codex_editor_list(argparse.Namespace())
        out = capsys.readouterr().out
        assert result == 0
        assert "Nenhum" in out

    def test_list_with_editors(self, nexus_env, capsys):
        from nexus._legacy_main import cmd_codex_editor_list

        editors = [EditorConfig(name="vim", command="vim", type="terminal")]
        save_editors(editors, "vim")

        result = cmd_codex_editor_list(argparse.Namespace())
        out = capsys.readouterr().out
        assert result == 0
        assert "vim" in out
        assert "terminal" in out
        assert "(padrão)" in out

    def test_list_multiple_editors(self, nexus_env, capsys):
        from nexus._legacy_main import cmd_codex_editor_list

        editors = [
            EditorConfig(name="vim", command="vim", type="terminal"),
            EditorConfig(name="code", command="code", type="gui"),
        ]
        save_editors(editors, "vim")

        result = cmd_codex_editor_list(argparse.Namespace())
        out = capsys.readouterr().out
        assert result == 0
        assert "vim" in out
        assert "code" in out
        assert "(padrão)" in out


class TestCmdCodexEditorAdd:
    def test_add_editor(self, nexus_env, mock_input, capsys):
        from nexus._legacy_main import cmd_codex_editor_add
        from nexus.editors import load_editors

        # add_editor() calls:
        #   input("  Nome ...") -> "vim"
        #   input("  Comando ...") -> "vim"
        #   _prompt_editor_type calls input(f"  [{default}]: ") -> "1" (terminal)
        mock_input.side_effect = ["vim", "vim", "1"]

        result = cmd_codex_editor_add(argparse.Namespace())
        out = capsys.readouterr().out
        assert result == 0
        assert "vim" in out

        editors, default = load_editors()
        assert len(editors) == 1
        assert editors[0].name == "vim"
        assert editors[0].command == "vim"
        assert editors[0].type == "terminal"
        assert default == "vim"

    def test_add_editor_empty_name_cancels(self, nexus_env, mock_input, capsys):
        from nexus._legacy_main import cmd_codex_editor_add
        from nexus.editors import load_editors

        mock_input.return_value = ""

        result = cmd_codex_editor_add(argparse.Namespace())
        out = capsys.readouterr().out
        assert result == 0  # editor_add returns None, cmd returns 0
        assert "Cancelado" in out

        editors, _ = load_editors()
        assert editors == []

    def test_add_gui_editor(self, nexus_env, mock_input, capsys):
        from nexus._legacy_main import cmd_codex_editor_add
        from nexus.editors import load_editors

        # name, command, type choice "2" = gui
        mock_input.side_effect = ["code", "code", "2"]

        result = cmd_codex_editor_add(argparse.Namespace())
        assert result == 0

        editors, default = load_editors()
        assert len(editors) == 1
        assert editors[0].type == "gui"


class TestCmdCodexEditorDefault:
    def test_set_default(self, nexus_env, mock_input, capsys):
        from nexus._legacy_main import cmd_codex_editor_default
        from nexus.editors import load_editors

        editors = [
            EditorConfig(name="vim", command="vim", type="terminal"),
            EditorConfig(name="nano", command="nano", type="terminal"),
        ]
        save_editors(editors, "vim")

        # Choose editor 2 (nano) as new default
        mock_input.return_value = "2"

        result = cmd_codex_editor_default(argparse.Namespace())
        out = capsys.readouterr().out
        assert result == 0
        assert "nano" in out

        _, default = load_editors()
        assert default == "nano"

    def test_set_default_empty(self, nexus_env, capsys):
        from nexus._legacy_main import cmd_codex_editor_default

        result = cmd_codex_editor_default(argparse.Namespace())
        out = capsys.readouterr().out
        assert result == 1
        assert "Nenhum editor" in out

    def test_set_default_invalid_choice(self, nexus_env, mock_input, capsys):
        from nexus._legacy_main import cmd_codex_editor_default

        editors = [EditorConfig(name="vim", command="vim", type="terminal")]
        save_editors(editors, "vim")

        mock_input.return_value = "99"

        result = cmd_codex_editor_default(argparse.Namespace())
        out = capsys.readouterr().out
        assert result == 1
        assert "inválida" in out

    def test_set_default_cancelled(self, nexus_env, mock_input, capsys):
        from nexus._legacy_main import cmd_codex_editor_default

        editors = [EditorConfig(name="vim", command="vim", type="terminal")]
        save_editors(editors, "vim")

        mock_input.side_effect = KeyboardInterrupt

        result = cmd_codex_editor_default(argparse.Namespace())
        out = capsys.readouterr().out
        assert result == 0
        assert "Cancelado" in out


class TestCmdCodexEditorRemove:
    def test_remove_editor(self, nexus_env, mock_input, capsys):
        from nexus._legacy_main import cmd_codex_editor_remove
        from nexus.editors import load_editors

        editors = [EditorConfig(name="vim", command="vim", type="terminal")]
        save_editors(editors, "vim")

        mock_input.return_value = "1"

        result = cmd_codex_editor_remove(argparse.Namespace())
        out = capsys.readouterr().out
        assert result == 0
        assert "vim" in out

        remaining, default = load_editors()
        assert remaining == []
        assert default == ""

    def test_remove_empty(self, nexus_env, capsys):
        from nexus._legacy_main import cmd_codex_editor_remove

        result = cmd_codex_editor_remove(argparse.Namespace())
        out = capsys.readouterr().out
        assert result == 0
        assert "Nenhum" in out

    def test_remove_invalid_choice(self, nexus_env, mock_input, capsys):
        from nexus._legacy_main import cmd_codex_editor_remove
        from nexus.editors import load_editors

        editors = [EditorConfig(name="vim", command="vim", type="terminal")]
        save_editors(editors, "vim")

        mock_input.return_value = "99"

        result = cmd_codex_editor_remove(argparse.Namespace())
        out = capsys.readouterr().out
        assert result == 1
        assert "inválida" in out

        remaining, _ = load_editors()
        assert len(remaining) == 1

    def test_remove_non_default_keeps_default(self, nexus_env, mock_input, capsys):
        from nexus._legacy_main import cmd_codex_editor_remove
        from nexus.editors import load_editors

        editors = [
            EditorConfig(name="vim", command="vim", type="terminal"),
            EditorConfig(name="nano", command="nano", type="terminal"),
        ]
        # vim is default, remove nano (choice 2) — default should stay vim
        save_editors(editors, "vim")

        mock_input.return_value = "2"

        result = cmd_codex_editor_remove(argparse.Namespace())
        assert result == 0

        remaining, default = load_editors()
        assert len(remaining) == 1
        assert remaining[0].name == "vim"
        assert default == "vim"

    def test_remove_default_shifts_to_next(self, nexus_env, mock_input, capsys):
        from nexus._legacy_main import cmd_codex_editor_remove
        from nexus.editors import load_editors

        editors = [
            EditorConfig(name="vim", command="vim", type="terminal"),
            EditorConfig(name="nano", command="nano", type="terminal"),
        ]
        # vim is default, remove vim (choice 1) — default should shift to nano
        save_editors(editors, "vim")

        mock_input.return_value = "1"

        result = cmd_codex_editor_remove(argparse.Namespace())
        assert result == 0

        remaining, default = load_editors()
        assert len(remaining) == 1
        assert remaining[0].name == "nano"
        assert default == "nano"

    def test_remove_cancelled(self, nexus_env, mock_input, capsys):
        from nexus._legacy_main import cmd_codex_editor_remove
        from nexus.editors import load_editors

        editors = [EditorConfig(name="vim", command="vim", type="terminal")]
        save_editors(editors, "vim")

        mock_input.side_effect = EOFError

        result = cmd_codex_editor_remove(argparse.Namespace())
        out = capsys.readouterr().out
        assert result == 0
        assert "Cancelado" in out

        remaining, _ = load_editors()
        assert len(remaining) == 1
