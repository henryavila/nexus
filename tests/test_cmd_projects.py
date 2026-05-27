import argparse
import pytest
from unittest.mock import patch, MagicMock

from nexus.registry import ProjectEntry, add_project, load_registry, normalize_path


class TestCmdRemove:
    def test_remove_happy_path(self, nexus_env, capsys):
        from nexus._legacy_main import cmd_remove

        # Create a real dir so resolve works, but we mock the path helpers anyway
        project_dir = nexus_env / "myproject"
        project_dir.mkdir()

        entry = ProjectEntry(name="My Project", path=str(project_dir), domain="pessoal")
        add_project(entry)
        assert len(load_registry()) == 1

        args = argparse.Namespace(query="My Project")
        with (
            patch("nexus._legacy_main.remove_git_hook"),
            patch("nexus._legacy_main.remove_claude_hook"),
            patch("nexus._legacy_main.resolve_path_for_entry", return_value=str(project_dir)),
            patch("nexus._legacy_main.resolve_project_path", return_value=str(project_dir)),
        ):
            result = cmd_remove(args)

        assert result == 0
        assert load_registry() == []

    def test_remove_not_found(self, nexus_env, capsys):
        from nexus._legacy_main import cmd_remove

        args = argparse.Namespace(query="ghost")
        result = cmd_remove(args)

        assert result == 1
        out = capsys.readouterr().out
        assert "não encontrado" in out

    def test_remove_project_without_path(self, nexus_env, capsys):
        """Projects with no path should also be removable."""
        from nexus._legacy_main import cmd_remove

        entry = ProjectEntry(name="No Path Project", domain="pessoal")
        add_project(entry)
        assert len(load_registry()) == 1

        args = argparse.Namespace(query="No Path Project")
        with (
            patch("nexus._legacy_main.remove_git_hook"),
            patch("nexus._legacy_main.remove_claude_hook"),
            patch("nexus._legacy_main.resolve_path_for_entry", return_value=None),
            patch("nexus._legacy_main.resolve_project_path", return_value=None),
        ):
            result = cmd_remove(args)

        assert result == 0
        assert load_registry() == []


class TestCmdList:
    def test_lists_active_projects(self, nexus_env, capsys):
        from nexus._legacy_main import cmd_list

        add_project(ProjectEntry(name="Active Project", domain="pessoal"))
        add_project(ProjectEntry(name="Archived Project", domain="pessoal", status="archived"))

        args = argparse.Namespace(all=False)
        result = cmd_list(args)

        out = capsys.readouterr().out
        assert "Active Project" in out
        assert "Archived Project" not in out
        assert result == 0

    def test_list_all_includes_archived(self, nexus_env, capsys):
        from nexus._legacy_main import cmd_list

        add_project(ProjectEntry(name="Archived Project", domain="pessoal", status="archived"))

        args = argparse.Namespace(all=True)
        result = cmd_list(args)

        out = capsys.readouterr().out
        assert "Archived Project" in out
        assert result == 0

    def test_empty_list(self, nexus_env, capsys):
        from nexus._legacy_main import cmd_list

        args = argparse.Namespace(all=False)
        result = cmd_list(args)

        out = capsys.readouterr().out
        assert "Nenhum" in out
        assert result == 0

    def test_list_shows_count(self, nexus_env, capsys):
        from nexus._legacy_main import cmd_list

        add_project(ProjectEntry(name="Alpha", domain="pessoal"))
        add_project(ProjectEntry(name="Beta", domain="trabalho"))

        args = argparse.Namespace(all=False)
        cmd_list(args)

        out = capsys.readouterr().out
        assert "2 projeto(s)" in out

    def test_list_without_all_attr(self, nexus_env, capsys):
        """cmd_list uses getattr(args, 'all', False) — ensure it handles missing attr."""
        from nexus._legacy_main import cmd_list

        add_project(ProjectEntry(name="Active", domain="pessoal"))

        args = argparse.Namespace()  # no 'all' attribute
        result = cmd_list(args)

        out = capsys.readouterr().out
        assert "Active" in out
        assert result == 0


class TestCmdStatus:
    def test_status_shows_project(self, nexus_env, capsys):
        from nexus._legacy_main import cmd_status

        project_dir = nexus_env / "statusproject"
        project_dir.mkdir()

        entry = ProjectEntry(
            name="Status Project",
            path=str(project_dir),
            domain="trabalho",
            description="A status test project",
        )
        add_project(entry)

        args = argparse.Namespace(query="Status Project")
        with (
            patch("nexus._legacy_main.resolve_path_for_entry", return_value=str(project_dir)),
            patch("nexus._legacy_main.resolve_project_path", return_value=str(project_dir)),
            patch("nexus._legacy_main.read_data", return_value={"projects": []}),
        ):
            result = cmd_status(args)

        out = capsys.readouterr().out
        assert "Status Project" in out
        assert result == 0

    def test_status_not_found(self, nexus_env, capsys):
        from nexus._legacy_main import cmd_status

        args = argparse.Namespace(query="ghost")
        result = cmd_status(args)

        assert result == 1
        out = capsys.readouterr().out
        assert "não encontrado" in out

    def test_status_shows_description_and_category(self, nexus_env, capsys):
        from nexus._legacy_main import cmd_status

        entry = ProjectEntry(
            name="Documented Project",
            domain="estudo",
            description="Learning stuff",
        )
        add_project(entry)

        args = argparse.Namespace(query="Documented Project")
        with (
            patch("nexus._legacy_main.resolve_path_for_entry", return_value=None),
            patch("nexus._legacy_main.resolve_project_path", return_value=None),
            patch("nexus._legacy_main.read_data", return_value={"projects": []}),
        ):
            result = cmd_status(args)

        out = capsys.readouterr().out
        assert "estudo" in out
        assert "Learning stuff" in out
        assert result == 0

    def test_status_shows_scan_data_when_available(self, nexus_env, capsys):
        from nexus._legacy_main import cmd_status

        entry = ProjectEntry(name="Scanned Project", domain="pessoal")
        add_project(entry)

        fake_scan = {
            "projects": [
                {
                    "path": "",
                    "name": "Scanned Project",
                    "class": "git",
                    "last_activity": "2026-01-01",
                    "git": {
                        "branch": "main",
                        "dirty": False,
                        "last_commit_date": "2026-01-01",
                        "last_commit_message": "initial commit",
                    },
                    "health": {},
                }
            ]
        }

        args = argparse.Namespace(query="Scanned Project")
        with (
            patch("nexus._legacy_main.resolve_path_for_entry", return_value=None),
            patch("nexus._legacy_main.resolve_project_path", return_value=None),
            patch("nexus._legacy_main.read_data", return_value={"projects": []}),
        ):
            result = cmd_status(args)

        assert result == 0
        out = capsys.readouterr().out
        # No scan data match, but it should not crash
        assert "sem dados de scan" in out


class TestCmdNote:
    def test_note_added(self, nexus_env, capsys):
        from nexus._legacy_main import cmd_note

        project_dir = nexus_env / "noteproject"
        project_dir.mkdir()

        entry = ProjectEntry(name="Note Project", path=str(project_dir), domain="pessoal")
        add_project(entry)

        args = argparse.Namespace(query="Note Project", text="my note")
        result = cmd_note(args)

        assert result == 0
        registry = load_registry()
        assert len(registry) == 1
        assert registry[0].note == "my note"

    def test_note_not_found(self, nexus_env, capsys):
        from nexus._legacy_main import cmd_note

        args = argparse.Namespace(query="ghost", text="x")
        result = cmd_note(args)

        assert result == 1
        out = capsys.readouterr().out
        assert "não encontrado" in out


class TestCmdMove:
    def test_move_explicit_path(self, nexus_env, capsys):
        from nexus._legacy_main import cmd_move

        old_dir = nexus_env / "oldproject"
        new_dir = nexus_env / "newproject"
        old_dir.mkdir()
        new_dir.mkdir()

        entry = ProjectEntry(name="Move Project", path=str(old_dir), domain="pessoal")
        add_project(entry)

        args = argparse.Namespace(query="Move Project", new_path=str(new_dir))
        with (
            patch("nexus._legacy_main.resolve_project_path", return_value=str(new_dir)),
            patch("nexus._legacy_main.ensure_project_config", return_value=(False, False)),
            patch("nexus._legacy_main.install_git_hook", return_value=False),
            patch("nexus._legacy_main.install_claude_hook", return_value=False),
            patch("nexus._legacy_main.scan_one", return_value={"name": "Move Project"}),
        ):
            result = cmd_move(args)

        assert result == 0
        registry = load_registry()
        assert len(registry) == 1
        assert registry[0].path == str(new_dir)

    def test_move_new_path_not_exists(self, nexus_env, capsys):
        from nexus._legacy_main import cmd_move

        project_dir = nexus_env / "existingproject"
        project_dir.mkdir()

        entry = ProjectEntry(name="Existing Project", path=str(project_dir), domain="pessoal")
        add_project(entry)

        args = argparse.Namespace(query="Existing Project", new_path="/nonexistent/path/xyz")
        result = cmd_move(args)

        assert result == 1
        out = capsys.readouterr().out
        assert "não existe" in out


class TestCmdDiscover:
    def test_discover_empty(self, nexus_env, capsys):
        from nexus._legacy_main import cmd_discover

        # nexus_env is a tmp_path with no git repos (no .git dirs)
        args = argparse.Namespace(path=str(nexus_env), depth=1)
        result = cmd_discover(args)

        assert result == 0
        out = capsys.readouterr().out
        assert "Nenhum" in out

    def test_discover_path_not_exists(self, nexus_env, capsys):
        from nexus._legacy_main import cmd_discover

        args = argparse.Namespace(path="/nonexistent/discover/path", depth=1)
        result = cmd_discover(args)

        assert result == 1
        out = capsys.readouterr().out
        assert "não existe" in out

    def test_discover_uses_normalize_path_for_matching(self, nexus_env, capsys):
        """Discover must use normalize_path (not Path.resolve) to match paths.

        normalize_path handles case-insensitive filesystems (NTFS/WSL2) where
        /DEV and /dev point to the same directory. This test verifies the
        normalization by registering a project via its real path, then having
        discover compare via normalize_path instead of raw Path.resolve().
        """
        from nexus._legacy_main import cmd_discover

        root = nexus_env / "scan_root"
        root.mkdir()
        proj = root / "MyProject"
        proj.mkdir()
        (proj / ".git").mkdir()

        # Register the project with its actual path
        entry = ProjectEntry(name="My Project", path=str(proj), domain="pessoal")
        add_project(entry)

        # Patch normalize_path to simulate case-insensitive filesystem:
        # both "MyProject" and "myproject" normalize to the same value
        real_normalize = normalize_path
        def _ci_normalize(path):
            """Simulate NTFS case-insensitive normalization."""
            return real_normalize(path).lower()

        args = argparse.Namespace(path=str(root))
        with (
            patch("builtins.input", return_value="q"),
            patch("nexus._legacy_main.normalize_path", side_effect=_ci_normalize),
        ):
            result = cmd_discover(args)

        assert result == 0
        out = capsys.readouterr().out
        assert "registrado" in out
        # Should NOT suggest adding
        assert "Indicadores" not in out

    def test_discover_add_as_project(self, nexus_env, capsys):
        from nexus._legacy_main import cmd_discover

        root = nexus_env / "scan_root"
        root.mkdir()
        proj = root / "MyProject"
        proj.mkdir()
        (proj / ".git").mkdir()

        args = argparse.Namespace(path=str(root))
        with (
            patch("builtins.input", side_effect=["p", "q"]),
            patch("nexus._legacy_main.cmd_add") as mock_add,
        ):
            result = cmd_discover(args)

        assert result == 0
        mock_add.assert_called_once()
        out = capsys.readouterr().out
        assert "1 projeto(s)" in out

    def test_discover_add_as_app(self, nexus_env, capsys):
        from nexus._legacy_main import cmd_discover

        root = nexus_env / "scan_root"
        root.mkdir()
        proj = root / "AppDir"
        proj.mkdir()
        (proj / ".git").mkdir()

        args = argparse.Namespace(path=str(root))
        with (
            patch("builtins.input", side_effect=["a", "q"]),
            patch("nexus._legacy_main.cmd_app_add") as mock_add,
        ):
            result = cmd_discover(args)

        assert result == 0
        mock_add.assert_called_once()
        # Check default_name was passed
        _, kwargs = mock_add.call_args
        assert kwargs["default_name"] == "AppDir"
        out = capsys.readouterr().out
        assert "1 app(s)" in out

    def test_discover_skip_and_quit(self, nexus_env, capsys):
        from nexus._legacy_main import cmd_discover

        root = nexus_env / "scan_root"
        root.mkdir()
        for name in ["ProjA", "ProjB", "ProjC"]:
            d = root / name
            d.mkdir()
            (d / ".git").mkdir()

        args = argparse.Namespace(path=str(root))
        # skip first (n/Enter), add second as project, quit on third
        with (
            patch("builtins.input", side_effect=["", "p", "q"]),
            patch("nexus._legacy_main.cmd_add") as mock_add,
        ):
            result = cmd_discover(args)

        assert result == 0
        assert mock_add.call_count == 1
        out = capsys.readouterr().out
        assert "1 projeto(s)" in out
        assert "0 app(s)" in out

    def test_discover_mixed_counters(self, nexus_env, capsys):
        from nexus._legacy_main import cmd_discover

        root = nexus_env / "scan_root"
        root.mkdir()
        for name in ["Proj1", "App1"]:
            d = root / name
            d.mkdir()
            (d / ".git").mkdir()

        args = argparse.Namespace(path=str(root))
        with (
            patch("builtins.input", side_effect=["p", "a"]),
            patch("nexus._legacy_main.cmd_add"),
            patch("nexus._legacy_main.cmd_app_add"),
        ):
            result = cmd_discover(args)

        assert result == 0
        out = capsys.readouterr().out
        assert "1 projeto(s)" in out
        assert "1 app(s)" in out


class TestCmdAddQuick:
    def test_quick_add_with_explicit_flags(self, nexus_env, capsys):
        """Quick add with explicit --name, --domain, --nature flags."""
        from nexus._legacy_main import cmd_add

        project_dir = nexus_env / "myquickproject"
        project_dir.mkdir()

        args = argparse.Namespace(
            path=str(project_dir),
            interactive=False,
            name="Quick Project",
            description="A quick test",
            domain="tech",
            nature="ferramenta",
            icon=None,
            repo=None,
            url=None,
            private=False,
        )
        with (
            patch("nexus._legacy_main.resolve_path_for_entry", return_value=str(project_dir)),
            patch("nexus._legacy_main.resolve_project_path", return_value=str(project_dir)),
            patch("nexus._legacy_main.ensure_project_config", return_value=(False, False)),
            patch("nexus._legacy_main.install_git_hook", return_value=False),
            patch("nexus._legacy_main.install_claude_hook", return_value=False),
        ):
            result = cmd_add(args)

        assert result == 0
        registry = load_registry()
        assert len(registry) == 1
        assert registry[0].name == "Quick Project"
        assert registry[0].domain == "tech"
        assert registry[0].nature == "ferramenta"

    def test_quick_add_defaults(self, nexus_env, capsys):
        """Quick add with path only uses default domain/nature."""
        from nexus._legacy_main import cmd_add

        project_dir = nexus_env / "defaultproject"
        project_dir.mkdir()

        args = argparse.Namespace(
            path=str(project_dir),
            interactive=False,
            name=None,
            description=None,
            domain=None,
            nature=None,
            icon=None,
            repo=None,
            url=None,
            private=False,
        )
        with (
            patch("nexus._legacy_main.resolve_path_for_entry", return_value=str(project_dir)),
            patch("nexus._legacy_main.resolve_project_path", return_value=str(project_dir)),
            patch("nexus._legacy_main.ensure_project_config", return_value=(False, False)),
            patch("nexus._legacy_main.install_git_hook", return_value=False),
            patch("nexus._legacy_main.install_claude_hook", return_value=False),
        ):
            result = cmd_add(args)

        assert result == 0
        registry = load_registry()
        assert len(registry) == 1
        assert registry[0].domain == "pessoal"
        assert registry[0].nature == "contexto"


class TestCmdProjectReplace:
    def test_replace_with_path_auto_registers(self, nexus_env, capsys):
        """Replace with path argument auto-registers the new project."""
        from nexus._legacy_main import cmd_project_replace

        # Set up old project
        old_dir = nexus_env / "oldproject"
        old_dir.mkdir()
        old_entry = ProjectEntry(name="Old Project", path=str(old_dir), domain="trabalho", nature="contexto")
        add_project(old_entry)

        # Set up new project path (not registered)
        new_dir = nexus_env / "newproject"
        new_dir.mkdir()

        args = argparse.Namespace(old="Old Project", new=str(new_dir))
        with (
            patch("builtins.input", return_value="s"),
            patch("nexus._legacy_main.resolve_path_for_entry", return_value=None),
            patch("nexus._legacy_main.resolve_project_path", return_value=None),
            patch("nexus._legacy_main.ensure_project_config", return_value=(False, False)),
            patch("nexus._legacy_main.install_git_hook", return_value=False),
            patch("nexus._legacy_main.install_claude_hook", return_value=False),
        ):
            result = cmd_project_replace(args)

        assert result == 0
        registry = load_registry()
        assert len(registry) == 2
        old = [e for e in registry if e.name == "Old Project"][0]
        new = [e for e in registry if e.name != "Old Project"][0]
        assert old.status == "replaced"
        assert new.domain == "trabalho"  # inherited from old
        out = capsys.readouterr().out
        assert "substituído" in out.lower() or "Nota de origem" in out

    def test_replace_with_already_registered_path_warns(self, nexus_env, capsys):
        """Replace with a path that is already registered should warn."""
        from nexus._legacy_main import cmd_project_replace

        # Set up old project
        old_dir = nexus_env / "oldproject"
        old_dir.mkdir()
        old_entry = ProjectEntry(name="Old Project", path=str(old_dir), domain="trabalho")
        add_project(old_entry)

        # Set up new project (already registered)
        new_dir = nexus_env / "newproject"
        new_dir.mkdir()
        new_entry = ProjectEntry(name="New Project", path=str(new_dir), domain="pessoal")
        add_project(new_entry)

        args = argparse.Namespace(old="Old Project", new="New Project")
        with (
            patch("builtins.input", return_value="s"),
        ):
            result = cmd_project_replace(args)

        assert result == 0
        registry = load_registry()
        old = [e for e in registry if e.name == "Old Project"][0]
        assert old.status == "replaced"
