import argparse
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from nexus.registry import ProjectEntry, save_registry


class CmdOpenTests(unittest.TestCase):
    def _setup_registry(self, td, entries):
        base = Path(td)
        projects_yml = base / "projects.yml"
        data_json = base / "data.json"
        data_json.write_text('{"version":"3.0","last_full_scan":null,"projects":[],"ideas":[]}')
        patches = [
            patch("nexus.registry.PROJECTS_YML", projects_yml),
            patch("nexus.registry.DATA_JSON", data_json),
            patch("nexus.registry.DATA_DIR", base),
        ]
        for p in patches:
            p.start()
        save_registry(entries)
        return patches

    def _teardown(self, patches):
        for p in patches:
            p.stop()

    def test_open_resolves_slug_and_launches(self):
        with tempfile.TemporaryDirectory() as td:
            proj_dir = Path(td) / "myproj"
            proj_dir.mkdir()
            entries = [ProjectEntry(path=str(proj_dir), name="My Project", slug="mp")]
            patches = self._setup_registry(td, entries)
            try:
                from nexus._legacy_main import cmd_open
                from nexus.cli_registry import CliEntry

                with patch("nexus._legacy_main.detect_clis", return_value=[CliEntry("claude", "claude", "Claude Code")]), \
                     patch("nexus._legacy_main.resolve_project_path", return_value=str(proj_dir)), \
                     patch("builtins.input", return_value="1"), \
                     patch("os.chdir") as mock_chdir, \
                     patch("os.execvp") as mock_exec:
                    code = cmd_open(argparse.Namespace(query="mp", shell=False))
                mock_chdir.assert_called_once_with(str(proj_dir))
                mock_exec.assert_called_once_with("claude", ["claude"])
            finally:
                self._teardown(patches)

    def test_open_not_found(self):
        with tempfile.TemporaryDirectory() as td:
            patches = self._setup_registry(td, [])
            try:
                from nexus._legacy_main import cmd_open
                with patch("nexus._legacy_main.detect_clis", return_value=[]):
                    code = cmd_open(argparse.Namespace(query="xyz", shell=False))
                self.assertEqual(code, 1)
            finally:
                self._teardown(patches)

    def test_open_no_clis_available(self):
        with tempfile.TemporaryDirectory() as td:
            proj_dir = Path(td) / "proj"
            proj_dir.mkdir()
            entries = [ProjectEntry(path=str(proj_dir), name="Proj", slug="proj")]
            patches = self._setup_registry(td, entries)
            try:
                from nexus._legacy_main import cmd_open
                with patch("nexus._legacy_main.detect_clis", return_value=[]), \
                     patch("nexus._legacy_main.resolve_project_path", return_value=str(proj_dir)):
                    code = cmd_open(argparse.Namespace(query="proj", shell=False))
                self.assertEqual(code, 1)
            finally:
                self._teardown(patches)

    def test_open_multiple_clis_prompts_user(self):
        with tempfile.TemporaryDirectory() as td:
            proj_dir = Path(td) / "proj"
            proj_dir.mkdir()
            entries = [ProjectEntry(path=str(proj_dir), name="Proj", slug="proj")]
            patches = self._setup_registry(td, entries)
            try:
                from nexus._legacy_main import cmd_open
                from nexus.cli_registry import CliEntry
                clis = [
                    CliEntry("claude", "claude", "Claude Code"),
                    CliEntry("codex", "codex", "Codex CLI"),
                ]
                with patch("nexus._legacy_main.detect_clis", return_value=clis), \
                     patch("nexus._legacy_main.resolve_project_path", return_value=str(proj_dir)), \
                     patch("builtins.input", return_value="1"), \
                     patch("os.chdir") as mock_chdir, \
                     patch("os.execvp") as mock_exec:
                    code = cmd_open(argparse.Namespace(query="proj", shell=False))
                mock_exec.assert_called_once_with("claude", ["claude"])
            finally:
                self._teardown(patches)


if __name__ == "__main__":
    unittest.main()
