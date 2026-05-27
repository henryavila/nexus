import argparse
import pytest
from unittest.mock import patch

from nexus.registry import ProjectEntry, add_project, load_registry
from nexus.apps import AppEntry, load_apps


class TestCmdConvertToApp:
    def test_convert_happy_path(self, nexus_env, mock_input, capsys):
        from nexus._legacy_main import cmd_project_convert_to_app

        project_dir = nexus_env / "myproject"
        project_dir.mkdir()
        entry = ProjectEntry(
            name="My Project", path=str(project_dir), slug="my-project",
            description="A project", icon="🚀", domain="tech",
            nature="ferramenta", private=True, url="https://example.com",
            repo="user/repo", note="some note", added="2025-01-01",
        )
        add_project(entry)

        mock_input.return_value = "s"

        result = cmd_project_convert_to_app(
            argparse.Namespace(query="my-project")
        )

        assert result == 0

        # Project removed
        assert load_registry() == []

        # App created with correct field mapping
        apps = load_apps()
        assert len(apps) == 1
        app = apps[0]
        assert app.name == "My Project"
        assert app.slug == "my-project"
        assert app.description == "A project"
        assert app.icon == "🚀"
        assert app.domain == "tech"
        assert app.github == "user/repo"
        assert app.url == "https://example.com"
        assert app.note == "some note"
        assert app.added == "2025-01-01"

        out = capsys.readouterr().out
        assert "Convertido" in out

    def test_convert_duplicate_slug_aborts(self, nexus_env, capsys):
        from nexus._legacy_main import cmd_project_convert_to_app
        from nexus.apps import add_app

        project_dir = nexus_env / "myproject"
        project_dir.mkdir()
        add_project(ProjectEntry(name="My Project", path=str(project_dir), slug="my-project"))
        add_app(AppEntry(name="Existing App", slug="my-project", domain="pessoal"))

        result = cmd_project_convert_to_app(
            argparse.Namespace(query="my-project")
        )

        assert result == 1
        # Project must NOT be removed
        assert len(load_registry()) == 1
        assert "já existe" in capsys.readouterr().out

    def test_convert_not_found(self, nexus_env, capsys):
        from nexus._legacy_main import cmd_project_convert_to_app

        result = cmd_project_convert_to_app(
            argparse.Namespace(query="nonexistent")
        )

        assert result == 1
        assert "não encontrado" in capsys.readouterr().out

    def test_convert_cancelled(self, nexus_env, mock_input, capsys):
        from nexus._legacy_main import cmd_project_convert_to_app

        project_dir = nexus_env / "myproject"
        project_dir.mkdir()
        add_project(ProjectEntry(name="My Project", path=str(project_dir), slug="my-project"))

        mock_input.return_value = "n"

        result = cmd_project_convert_to_app(
            argparse.Namespace(query="my-project")
        )

        assert result == 0
        # Project NOT removed
        assert len(load_registry()) == 1
        assert load_apps() == []

    def test_convert_ambiguous(self, nexus_env, capsys):
        from nexus._legacy_main import cmd_project_convert_to_app

        add_project(ProjectEntry(name="Alpha Project", slug="alpha-project"))
        add_project(ProjectEntry(name="Alpha Service", slug="alpha-service"))

        result = cmd_project_convert_to_app(
            argparse.Namespace(query="alpha")
        )

        assert result == 1
        assert "ambíguo" in capsys.readouterr().out.lower()

    def test_convert_shows_discarded_fields(self, nexus_env, mock_input, capsys):
        from nexus._legacy_main import cmd_project_convert_to_app

        project_dir = nexus_env / "myproject"
        project_dir.mkdir()
        add_project(ProjectEntry(
            name="My Project", path=str(project_dir), slug="my-project",
            nature="ferramenta", private=True, status="active",
        ))

        mock_input.return_value = "n"  # cancel to just check output

        cmd_project_convert_to_app(argparse.Namespace(query="my-project"))

        out = capsys.readouterr().out
        assert "descartados" in out.lower() or "Descartados" in out

    def test_convert_atomicity(self, nexus_env, mock_input, capsys):
        """Project must NOT be removed if add_app raises."""
        from nexus._legacy_main import cmd_project_convert_to_app

        project_dir = nexus_env / "myproject"
        project_dir.mkdir()
        add_project(ProjectEntry(name="My Project", path=str(project_dir), slug="my-project"))
        mock_input.return_value = "s"

        with patch("nexus.apps.add_app", side_effect=RuntimeError("db error")):
            result = cmd_project_convert_to_app(argparse.Namespace(query="my-project"))

        assert result == 1
        assert len(load_registry()) == 1  # project must survive
        assert "Erro" in capsys.readouterr().out
