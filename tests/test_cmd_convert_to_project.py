import argparse
import pytest
from unittest.mock import patch

from nexus.registry import ProjectEntry, add_project, load_registry
from nexus.apps import AppEntry, add_app, load_apps


class TestCmdConvertToProject:
    def test_convert_happy_path(self, nexus_env, mock_input, capsys):
        from nexus._legacy_main import cmd_app_convert_to_project

        project_dir = nexus_env / "myapp"
        project_dir.mkdir()
        add_app(AppEntry(
            name="My App", slug="my-app", description="An app",
            icon="\U0001f680", domain="tech", github="user/repo",
            url="https://example.com", note="some note", added="2025-01-01",
        ))

        # path, nature choice (2=ferramenta), confirm
        mock_input.side_effect = [str(project_dir), "2", "s"]

        with (
            patch("nexus._legacy_main.resolve_path_for_entry", return_value=str(project_dir)),
            patch("nexus._legacy_main.resolve_project_path", return_value=str(project_dir)),
            patch("nexus._legacy_main.ensure_project_config", return_value=(False, False)),
            patch("nexus._legacy_main.install_git_hook", return_value=False),
            patch("nexus._legacy_main.install_claude_hook", return_value=False),
        ):
            result = cmd_app_convert_to_project(argparse.Namespace(query="my-app"))

        assert result == 0
        assert load_apps() == []

        projects = load_registry()
        assert len(projects) == 1
        p = projects[0]
        assert p.name == "My App"
        assert p.slug == "my-app"
        assert p.description == "An app"
        assert p.icon == "\U0001f680"
        assert p.domain == "tech"
        assert p.repo == "user/repo"
        assert p.url == "https://example.com"
        assert p.note == "some note"
        assert p.added == "2025-01-01"
        assert p.nature == "ferramenta"  # choice 2

        assert "Convertido" in capsys.readouterr().out

    def test_convert_duplicate_slug_aborts(self, nexus_env, capsys):
        from nexus._legacy_main import cmd_app_convert_to_project

        add_app(AppEntry(name="My App", slug="my-app", domain="pessoal"))
        add_project(ProjectEntry(name="Existing", slug="my-app"))

        result = cmd_app_convert_to_project(argparse.Namespace(query="my-app"))

        assert result == 1
        assert len(load_apps()) == 1  # app preserved
        assert "já existe" in capsys.readouterr().out

    def test_convert_not_found(self, nexus_env, capsys):
        from nexus._legacy_main import cmd_app_convert_to_project

        result = cmd_app_convert_to_project(argparse.Namespace(query="nonexistent"))

        assert result == 1
        assert "não encontrado" in capsys.readouterr().out

    def test_convert_cancelled(self, nexus_env, mock_input, capsys):
        from nexus._legacy_main import cmd_app_convert_to_project

        add_app(AppEntry(name="My App", slug="my-app", domain="pessoal"))

        # path (skip), nature (1=contexto), cancel
        mock_input.side_effect = ["", "1", "n"]

        result = cmd_app_convert_to_project(argparse.Namespace(query="my-app"))

        assert result == 0
        assert len(load_apps()) == 1  # app preserved
        assert load_registry() == []

    def test_convert_no_path(self, nexus_env, mock_input, capsys):
        from nexus._legacy_main import cmd_app_convert_to_project

        add_app(AppEntry(name="My App", slug="my-app", domain="tech"))

        # empty path, nature (1=contexto), confirm
        mock_input.side_effect = ["", "1", "s"]

        result = cmd_app_convert_to_project(argparse.Namespace(query="my-app"))

        assert result == 0
        projects = load_registry()
        assert len(projects) == 1
        assert projects[0].path is None
        assert projects[0].nature == "contexto"

    def test_convert_invalid_path(self, nexus_env, mock_input, capsys):
        from nexus._legacy_main import cmd_app_convert_to_project

        add_app(AppEntry(name="My App", slug="my-app", domain="pessoal"))
        mock_input.side_effect = ["/nonexistent/path"]

        result = cmd_app_convert_to_project(argparse.Namespace(query="my-app"))

        assert result == 1
        assert len(load_apps()) == 1  # app preserved
        assert "não existe" in capsys.readouterr().out

    def test_convert_ambiguous(self, nexus_env, capsys):
        from nexus._legacy_main import cmd_app_convert_to_project

        add_app(AppEntry(name="Alpha App", slug="alpha-app", domain="tech"))
        add_app(AppEntry(name="Alpha Service", slug="alpha-service", domain="tech"))

        result = cmd_app_convert_to_project(argparse.Namespace(query="alpha"))

        assert result == 1
        out = capsys.readouterr().out
        assert "ambíguo" in out.lower() or "Matches" in out

    def test_convert_atomicity(self, nexus_env, mock_input, capsys):
        """App must NOT be removed if add_project fails."""
        from nexus._legacy_main import cmd_app_convert_to_project

        add_app(AppEntry(name="My App", slug="my-app", domain="pessoal"))

        # empty path, nature (1=contexto), confirm
        mock_input.side_effect = ["", "1", "s"]

        with patch("nexus._legacy_main.add_project", return_value=(False, None)):
            result = cmd_app_convert_to_project(argparse.Namespace(query="my-app"))

        assert result == 1
        assert len(load_apps()) == 1  # app must survive
        assert "Erro" in capsys.readouterr().out
