"""Tests for cmd_push and cmd_open edge cases (Task 10)."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from nexus.apps import AppEntry, add_app
from nexus.environment import EnvironmentEntry, load_environments, save_environments
from nexus.registry import ProjectEntry, save_registry


# ---------------------------------------------------------------------------
# TestCmdPush
# ---------------------------------------------------------------------------

class TestCmdPush:
    """Tests for cmd_push — complex multi-step publish pipeline."""

    def test_push_pull_failure_aborts(self, nexus_env, capsys):
        """If pull_rebase on the nexus repo fails, cmd_push returns 1."""
        from nexus._legacy_main import cmd_push

        # pull_rebase is imported late inside cmd_push via `from .sync import pull_rebase`,
        # so it must be patched in nexus.sync (the source module).
        with (
            patch("nexus.NEXUS_ROOT", nexus_env),
            patch("nexus.sync.pull_rebase", return_value=(False, "conflict detected")),
        ):
            result = cmd_push(argparse.Namespace())

        assert result == 1
        out = capsys.readouterr().out
        assert "falhou" in out

    def test_push_no_portal_aborts(self, nexus_env, capsys):
        """If portal dir doesn't exist after clone attempt, return 1."""
        from nexus._legacy_main import cmd_push

        # data.json must exist because cmd_push does `from . import DATA_JSON`
        # and later shutil.copy2 it; but we abort before that point.
        # pull_rebase succeeds for nexus repo — portal clone attempt fails
        # (subprocess.run for git clone doesn't create the dir).

        # We need scan_all mocked so we don't actually scan
        mock_data = {"projects": [], "ideas": [], "version": "3.0"}

        def fake_pull_rebase(path):
            # First call: nexus repo OK; second call would be portal (never reached)
            return True, "Already up to date."

        with (
            patch("nexus.NEXUS_ROOT", nexus_env),
            patch("nexus.sync.pull_rebase", side_effect=fake_pull_rebase),
            patch("nexus._legacy_main.scan_all", return_value=mock_data),
            patch("nexus._legacy_main.load_registry", return_value=[]),
            patch("nexus._legacy_main.subprocess.run", return_value=MagicMock(returncode=0)),
        ):
            result = cmd_push(argparse.Namespace())

        # Portal dir was never created → should abort with return code 1
        assert result == 1
        out = capsys.readouterr().out
        assert "portal" in out.lower()

    def test_push_no_changes(self, nexus_env, capsys):
        """If git diff --cached --quiet returns 0, no commit is made and 0 is returned."""
        from nexus._legacy_main import cmd_push

        # Create portal dir and frontend dir under nexus_env
        portal_dir = nexus_env / "web"
        portal_dir.mkdir()
        frontend_dir = nexus_env / "frontend"
        frontend_dir.mkdir()

        # data.json must exist for shutil.copy2
        data_json = nexus_env / "data.json"
        data_json.write_text(json.dumps({"version": "3.0", "projects": [], "ideas": []}))

        mock_data = {"projects": [], "ideas": [], "version": "3.0"}

        def fake_subprocess_run(cmd, *args, **kwargs):
            mock = MagicMock()
            mock.returncode = 0
            mock.stdout = ""
            mock.stderr = ""
            return mock

        def fake_pull_rebase(path):
            return True, "Already up to date."

        with (
            patch("nexus.NEXUS_ROOT", nexus_env),
            patch("nexus.DATA_JSON", data_json),
            patch("nexus.sync.pull_rebase", side_effect=fake_pull_rebase),
            patch("nexus._legacy_main.scan_all", return_value=mock_data),
            patch("nexus._legacy_main.load_registry", return_value=[]),
            patch("nexus._legacy_main.subprocess.run", side_effect=fake_subprocess_run),
        ):
            result = cmd_push(argparse.Namespace())

        assert result == 0
        out = capsys.readouterr().out
        assert "mudança" in out or "Nenhuma" in out


# ---------------------------------------------------------------------------
# TestCmdOpen
# ---------------------------------------------------------------------------

class TestCmdOpen:
    """Additional edge-case tests for cmd_open."""

    def _add_project(self, nexus_env):
        """Helper: create a real dir + project entry for use in tests."""
        proj_dir = nexus_env / "my_proj"
        proj_dir.mkdir(exist_ok=True)
        entry = ProjectEntry(
            name="My Project",
            slug="myproj",
            path=str(proj_dir),
            domain="pessoal",
        )
        save_registry([entry])
        return proj_dir, entry

    def test_open_project_execs(self, nexus_env, capsys):
        """cmd_open resolves a project and calls os.execvp with the chosen CLI."""
        from nexus._legacy_main import cmd_open
        from nexus.cli_registry import CliEntry

        proj_dir, _entry = self._add_project(nexus_env)

        with (
            patch("nexus._legacy_main.detect_clis", return_value=[CliEntry("claude", "claude", "Claude Code")]),
            patch("nexus._legacy_main.resolve_path_for_entry", return_value=str(proj_dir)),
            patch("nexus._legacy_main.resolve_project_path", return_value=str(proj_dir)),
            patch("builtins.input", return_value="1"),
            patch("os.chdir") as mock_chdir,
            patch("os.execvp") as mock_exec,
        ):
            result = cmd_open(argparse.Namespace(query="myproj", shell=False))

        mock_exec.assert_called_once_with("claude", ["claude"])
        mock_chdir.assert_called_once_with(str(proj_dir))

    def test_open_not_found(self, nexus_env, capsys):
        """cmd_open returns 1 when the query doesn't match any project or app."""
        from nexus._legacy_main import cmd_open
        from nexus.apps import AppEntry

        result = cmd_open(argparse.Namespace(query="ghost", shell=False))

        assert result == 1
        out = capsys.readouterr().out
        assert "não encontrado" in out or "ghost" in out

    def test_open_shell_flag_execs_shell(self, nexus_env, capsys):
        """When --shell flag is set, cmd_open opens the project dir in a shell."""
        import os
        from nexus._legacy_main import cmd_open
        from nexus.cli_registry import CliEntry

        proj_dir, _entry = self._add_project(nexus_env)

        # --shell path comes after CLI detection, so we need at least one CLI
        with (
            patch("nexus._legacy_main.detect_clis", return_value=[CliEntry("claude", "claude", "Claude Code")]),
            patch("nexus._legacy_main.resolve_path_for_entry", return_value=str(proj_dir)),
            patch("nexus._legacy_main.resolve_project_path", return_value=str(proj_dir)),
            patch.dict(os.environ, {"SHELL": "/bin/bash"}),
            patch("os.chdir") as mock_chdir,
            patch("os.execvp") as mock_exec,
        ):
            result = cmd_open(argparse.Namespace(query="myproj", shell=True))

        mock_exec.assert_called_once_with("/bin/bash", ["/bin/bash"])
        mock_chdir.assert_called_once_with(str(proj_dir))

    @patch("nexus.environment.get_current_hostname", return_value="HOST")
    def test_open_app_with_env_path_execs(self, _mock_host, nexus_env, capsys):
        """cmd_open opens an app in a CLI when the current environment has a path."""
        from nexus._legacy_main import cmd_open
        from nexus.cli_registry import CliEntry

        app_dir = nexus_env / "myapp"
        app_dir.mkdir()
        add_app(AppEntry(name="My App", slug="myapp", domain="pessoal"))
        save_environments([
            EnvironmentEntry(
                hostname="HOST",
                name="Host",
                location="Casa",
                paths={"myapp": str(app_dir)},
            )
        ])

        with (
            patch("nexus._legacy_main.detect_clis", return_value=[CliEntry("claude", "claude", "Claude Code")]),
            patch("nexus._legacy_main.resolve_project_path", return_value=str(app_dir)),
            patch("builtins.input", return_value="1"),
            patch("os.chdir") as mock_chdir,
            patch("os.execvp") as mock_exec,
        ):
            cmd_open(argparse.Namespace(query="myapp", shell=False))

        mock_chdir.assert_called_once_with(str(app_dir))
        mock_exec.assert_called_once_with("claude", ["claude"])


class TestCmdScanPathRegistration:
    @patch("nexus.environment.get_current_hostname", return_value="HOST")
    @patch("nexus._legacy_main.get_current_hostname", return_value="HOST")
    def test_scan_project_path_registers_matching_app(self, _main_host, _env_host, nexus_env, capsys):
        """cmd_scan learns the current environment path for a matching app directory."""
        from nexus._legacy_main import cmd_scan

        app_dir = nexus_env / "nexus"
        app_dir.mkdir()
        add_app(AppEntry(name="nexus", slug="nexus", domain="tech"))
        save_environments([
            EnvironmentEntry(
                hostname="HOST",
                name="Host",
                location="Casa",
            )
        ])

        with patch("nexus._legacy_main.scan_one") as mock_scan_one:
            result = cmd_scan(argparse.Namespace(project=str(app_dir), sync_project_config=False))

        assert result == 0
        assert load_environments()[0].paths["nexus"] == str(app_dir.resolve())
        mock_scan_one.assert_not_called()
        out = capsys.readouterr().out
        assert "app" in out.lower() or "path" in out.lower()
