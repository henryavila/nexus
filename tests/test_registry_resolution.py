import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nexus.registry import ProjectEntry, resolve_project, save_registry


class RegistryResolutionTests(unittest.TestCase):
    def test_resolve_partial_query_returns_ambiguous_matches(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            projects_yml = base / "projects.yml"
            data_json = base / "data.json"
            data_json.write_text('{"version":"1.0","last_full_scan":null,"projects":[]}', encoding="utf-8")

            entries = [
                ProjectEntry(path="/tmp/nexus", name="nexus", added="2026-02-20"),
                ProjectEntry(path="/tmp/henry", name="henry", added="2026-02-20"),
            ]

            with patch("nexus.registry.PROJECTS_YML", projects_yml), patch("nexus.registry.DATA_JSON", data_json), patch("nexus.registry.DATA_DIR", base):
                save_registry(entries)
                found, ambiguous = resolve_project("tmp")

            self.assertIsNone(found)
            self.assertEqual(len(ambiguous), 2)


class ResolveBySlugTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.tmpdir.name)
        self.yml = self.data_dir / "projects.yml"
        self.json = self.data_dir / "data.json"
        self.json.write_text('{"version":"3.0","last_full_scan":null,"projects":[],"ideas":[]}')
        self.patches = [
            patch("nexus.registry.PROJECTS_YML", self.yml),
            patch("nexus.registry.DATA_JSON", self.json),
            patch("nexus.registry.DATA_DIR", self.data_dir),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.tmpdir.cleanup()

    def test_resolve_exact_slug_match(self):
        entries = [
            ProjectEntry(path="/tmp/dragon", name="Dragon Heir", slug="dh"),
            ProjectEntry(path="/tmp/nexus", name="nexus", slug="nexus"),
        ]
        save_registry(entries)
        found, ambiguous = resolve_project("dh")
        self.assertIsNotNone(found)
        self.assertEqual(found.name, "Dragon Heir")
        self.assertEqual(ambiguous, [])

    def test_slug_takes_priority_over_partial_name(self):
        """If slug matches exactly, it wins even if name partial also matches."""
        entries = [
            ProjectEntry(path="/tmp/a", name="dh-tools", slug="dh-tools"),
            ProjectEntry(path="/tmp/b", name="Dragon Heir", slug="dh"),
        ]
        save_registry(entries)
        found, _ = resolve_project("dh")
        self.assertEqual(found.name, "Dragon Heir")

    def test_slug_match_is_case_insensitive(self):
        entries = [
            ProjectEntry(path="/tmp/x", name="CRCMG", slug="crcmg"),
        ]
        save_registry(entries)
        found, _ = resolve_project("CRCMG")
        self.assertIsNotNone(found)
        self.assertEqual(found.slug, "crcmg")


if __name__ == "__main__":
    unittest.main()
