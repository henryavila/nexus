import argparse
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nexus.registry import ProjectEntry, save_registry


class TestCliProjectConfig(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.tmpdir.name) / "data"
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.yml = self.data_dir / "projects.yml"
        self.json = self.data_dir / "data.json"
        self.lock = self.data_dir / ".nexus.lock"

        self.project = Path(self.tmpdir.name) / "demo-project"
        self.project.mkdir(parents=True, exist_ok=True)

        self.patches = [
            patch("nexus.registry.PROJECTS_YML", self.yml),
            patch("nexus.registry.DATA_JSON", self.json),
            patch("nexus.registry.DATA_DIR", self.data_dir),
            patch("nexus.scanner.DATA_JSON", self.json),
            patch("nexus.scanner.LOCK_FILE", self.lock),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.tmpdir.cleanup()

    def test_scan_parser_has_sync_project_config_flag(self):
        from nexus._legacy_main import build_parser

        args = build_parser().parse_args(["scan", "--sync-project-config"])
        self.assertTrue(args.sync_project_config)

    def test_add_creates_nexus_yaml(self):
        from nexus._legacy_main import cmd_add

        answers = iter([
            "",   # nome
            "",   # descrição
            "1",  # categoria
            "1",           # nature
            "",   # ícone
            "",   # url
            "",   # repo
            "n",  # web config
        ])

        with patch("builtins.input", side_effect=lambda _prompt="": next(answers)):
            with patch("nexus._legacy_main.install_git_hook", return_value=False):
                with patch("nexus._legacy_main.install_claude_hook", return_value=False):
                    code = cmd_add(argparse.Namespace(path=str(self.project)))

        self.assertEqual(code, 0)
        self.assertTrue((self.project / "nexus.yaml").exists())

    def test_scan_with_sync_generates_project_config(self):
        from nexus._legacy_main import cmd_scan

        save_registry(
            [
                ProjectEntry(
                    path=str(self.project),
                    name="Demo",
                    domain="pessoal",
                    added="2026-02-26",
                )
            ]
        )

        with patch("nexus._legacy_main.install_git_hook", return_value=False):
            with patch("nexus._legacy_main.install_claude_hook", return_value=False):
                code = cmd_scan(argparse.Namespace(project=None, sync_project_config=True))

        self.assertEqual(code, 0)
        self.assertTrue((self.project / "nexus.yaml").exists())

    def test_scan_applies_nexus_yaml_overrides_to_output(self):
        from nexus._legacy_main import cmd_scan

        save_registry(
            [
                ProjectEntry(
                    path=str(self.project),
                    name="Nome Registry",
                    domain="pessoal",
                    added="2026-02-26",
                )
            ]
        )

        (self.project / "nexus.yaml").write_text(
            "schema_version: 1\n"
            "project:\n"
            "  name: Nome Local\n",
            encoding="utf-8",
        )

        with patch("nexus._legacy_main.install_git_hook", return_value=False):
            with patch("nexus._legacy_main.install_claude_hook", return_value=False):
                code = cmd_scan(argparse.Namespace(project=None, sync_project_config=False))

        self.assertEqual(code, 0)
        payload = json.loads(self.json.read_text(encoding="utf-8"))
        self.assertEqual(payload["projects"][0]["name"], "Nome Local")


    def test_edit_syncs_nexus_yaml(self):
        from nexus._legacy_main import cmd_edit

        save_registry(
            [
                ProjectEntry(
                    path=str(self.project),
                    name="Demo",
                    domain="pessoal",
                    added="2026-02-26",
                )
            ]
        )

        answers = iter([
            "",         # nome (keep)
            "",         # slug (keep)
            "",         # descrição (keep)
            "",         # ícone (keep)
            "",         # url (keep)
            "",         # repo (keep)
            "1",        # categoria (keep first)
            "1",           # nature
            "",         # status (keep)
            "n",        # web config
        ])

        with patch("builtins.input", side_effect=lambda _prompt="": next(answers)):
            code = cmd_edit(argparse.Namespace(query="Demo"))

        self.assertEqual(code, 0)
        self.assertTrue((self.project / "nexus.yaml").exists())


if __name__ == "__main__":
    unittest.main()
