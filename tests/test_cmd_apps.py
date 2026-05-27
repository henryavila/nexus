import pytest
from unittest.mock import patch
from nexus.apps import AppEntry, add_app, load_apps


class TestCmdAppList:
    def test_lists_apps(self, nexus_env, capsys):
        from nexus._legacy_main import cmd_app_list
        add_app(AppEntry(name="My App", description="Desc", domain="pessoal"))
        cmd_app_list()
        out = capsys.readouterr().out
        assert "My App" in out
        assert "pessoal" in out

    def test_empty_list(self, nexus_env, capsys):
        from nexus._legacy_main import cmd_app_list
        cmd_app_list()
        out = capsys.readouterr().out
        assert "Nenhum app" in out


class TestCmdAppAdd:
    def test_add_app_happy_path(self, nexus_env, mock_input):
        from nexus._legacy_main import cmd_app_add
        # _prompt_choice reads via input("> "), "6" = "pessoal" in sorted list
        mock_input.side_effect = [
            "Test App",       # name
            "A test app",     # description
            "6",              # category choice (sorted: Empreendimentos,estudo,ferramentas,games,igreja,pessoal,trabalho)
            "",               # icon
            "",               # github
            "https://x.com",  # url
        ]
        cmd_app_add()
        apps = load_apps()
        assert len(apps) == 1
        assert apps[0].name == "Test App"
        assert apps[0].url == "https://x.com"

    def test_add_app_empty_name_aborts(self, nexus_env, mock_input, capsys):
        from nexus._legacy_main import cmd_app_add
        mock_input.return_value = ""  # empty name
        cmd_app_add()
        assert load_apps() == []
        assert "obrigatório" in capsys.readouterr().out

    def test_add_app_ctrl_c(self, nexus_env, mock_input, capsys):
        from nexus._legacy_main import cmd_app_add
        mock_input.side_effect = KeyboardInterrupt
        cmd_app_add()
        assert load_apps() == []


class TestCmdAppRemove:
    def test_remove_confirmed(self, nexus_env, mock_input, capsys):
        from nexus._legacy_main import cmd_app_remove
        add_app(AppEntry(name="To Remove", domain="pessoal"))
        mock_input.return_value = "s"
        cmd_app_remove("to-remove")
        assert load_apps() == []
        assert "removido" in capsys.readouterr().out

    def test_remove_cancelled(self, nexus_env, mock_input):
        from nexus._legacy_main import cmd_app_remove
        add_app(AppEntry(name="Keep Me", domain="pessoal"))
        mock_input.return_value = "n"
        cmd_app_remove("keep-me")
        assert len(load_apps()) == 1

    def test_remove_not_found(self, nexus_env, capsys):
        from nexus._legacy_main import cmd_app_remove
        cmd_app_remove("nonexistent")
        assert "não encontrado" in capsys.readouterr().out


class TestCmdAppEdit:
    def test_edit_updates_fields(self, nexus_env, mock_input, capsys):
        from nexus._legacy_main import cmd_app_edit
        add_app(AppEntry(name="Original", description="Old", domain="pessoal"))
        mock_input.side_effect = [
            "Updated",    # name
            "New desc",   # description
            "",           # category (keep)
            "",           # icon
            "",           # github
            "",           # url
        ]
        cmd_app_edit("original")
        apps = load_apps()
        assert apps[0].name == "Updated"
        assert apps[0].description == "New desc"

    def test_edit_not_found(self, nexus_env, capsys):
        from nexus._legacy_main import cmd_app_edit
        cmd_app_edit("nonexistent")
        assert "não encontrado" in capsys.readouterr().out


class TestCmdAppNote:
    def test_note_saved(self, nexus_env, mock_input, capsys):
        from nexus._legacy_main import cmd_app_note
        add_app(AppEntry(name="Note App", domain="pessoal"))
        mock_input.return_value = "my note"
        with patch("nexus._legacy_main.find_environment", return_value=None):
            cmd_app_note("note-app")
        apps = load_apps()
        assert apps[0].note == "my note"

    def test_note_empty_ignored(self, nexus_env, mock_input, capsys):
        from nexus._legacy_main import cmd_app_note
        add_app(AppEntry(name="No Note", domain="pessoal"))
        mock_input.return_value = ""
        with patch("nexus._legacy_main.find_environment", return_value=None):
            cmd_app_note("no-note")
        assert "vazia" in capsys.readouterr().out


class TestCmdAppDispatcher:
    def test_unknown_subcmd(self, nexus_env, capsys):
        from nexus._legacy_main import cmd_app
        import argparse
        result = cmd_app(argparse.Namespace(app_cmd="unknown", query=None))
        assert result == 1

    def test_remove_no_query(self, nexus_env, capsys):
        from nexus._legacy_main import cmd_app
        import argparse
        result = cmd_app(argparse.Namespace(app_cmd="remove", query=None))
        assert result == 1
