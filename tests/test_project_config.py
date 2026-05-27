import tempfile
import unittest
from pathlib import Path

import yaml

from nexus.project_config import (
    PROJECT_CONFIG_FILENAME,
    apply_project_overrides,
    ensure_project_config,
    load_project_config,
    resolve_project_path,
    set_project_path_override,
)
from nexus.registry import ProjectEntry


class TestProjectConfig(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)
        self.project = self.root / "project"
        self.project.mkdir(parents=True, exist_ok=True)
        self.alt_project = self.root / "project-local"
        self.alt_project.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_ensure_creates_full_template_with_empty_values(self):
        created, updated = ensure_project_config(str(self.project))
        self.assertTrue(created)
        self.assertFalse(updated)

        cfg_path = self.project / PROJECT_CONFIG_FILENAME
        self.assertTrue(cfg_path.exists())

        text = cfg_path.read_text(encoding="utf-8")
        self.assertIn("schema_version: 1", text)
        self.assertIn("local:", text)
        self.assertIn("Override de caminho apenas para esta máquina", text)

        cfg = load_project_config(str(self.project))
        self.assertIsNone(cfg["project"]["name"])
        self.assertIsNone(cfg["project"]["status"])
        self.assertIsNone(cfg["web"]["route"])
        self.assertIsNone(cfg["local"]["path_override"])

    def test_ensure_preserves_existing_and_adds_missing_fields(self):
        cfg_path = self.project / PROJECT_CONFIG_FILENAME
        cfg_path.write_text(
            "schema_version: 1\n"
            "project:\n"
            "  name: Nome Local\n",
            encoding="utf-8",
        )

        created, updated = ensure_project_config(str(self.project))
        self.assertFalse(created)
        self.assertTrue(updated)

        cfg = load_project_config(str(self.project))
        self.assertEqual(cfg["project"]["name"], "Nome Local")
        self.assertIn("web", cfg)
        self.assertIn("local", cfg)
        self.assertIn("status", cfg["project"])

    def test_resolve_project_path_uses_local_path_override(self):
        ensure_project_config(str(self.project))
        set_project_path_override(str(self.project), str(self.alt_project))

        resolved = resolve_project_path(str(self.project))
        self.assertEqual(resolved, str(self.alt_project.resolve()))

    def test_set_override_writes_to_local_path_when_canonical_missing(self):
        """Bug fix: set_project_path_override should write nexus.yaml to
        local_path when the canonical path doesn't exist on this machine."""
        missing = self.root / "nonexistent"
        # missing does NOT exist — simulates canonical path from another machine
        ok = set_project_path_override(str(missing), str(self.alt_project))
        self.assertTrue(ok)

        cfg = load_project_config(str(self.alt_project))
        self.assertEqual(cfg["local"]["path_override"], str(self.alt_project.resolve()))
        self.assertTrue((self.alt_project / PROJECT_CONFIG_FILENAME).exists())

    def test_set_override_returns_false_when_both_paths_missing(self):
        missing_a = self.root / "nonexistent-a"
        missing_b = self.root / "nonexistent-b"
        ok = set_project_path_override(str(missing_a), str(missing_b))
        self.assertFalse(ok)

    def test_apply_project_overrides_merges_project_and_web(self):
        cfg_path = self.project / PROJECT_CONFIG_FILENAME
        cfg_path.write_text(
            yaml.safe_dump(
                {
                    "schema_version": 1,
                    "project": {"name": "Nome Local", "status": "archived"},
                    "web": {"route": "/local"},
                    "local": {"path_override": None},
                },
                sort_keys=False,
                allow_unicode=True,
            ),
            encoding="utf-8",
        )
        ensure_project_config(str(self.project))

        entry = ProjectEntry(
            path=str(self.project),
            name="Nome Registry",
            domain="pessoal",
            web={"route": "/old", "static_dir": "dist"},
        )
        merged = apply_project_overrides(entry)

        self.assertEqual(merged.name, "Nome Local")
        self.assertEqual(merged.status, "archived")
        self.assertIsNotNone(merged.web)
        self.assertEqual(merged.web["route"], "/local")
        self.assertEqual(merged.web["static_dir"], "dist")


class ProjectConfigSlugTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)
        self.project = self.root / "project"
        self.project.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_slug_in_default_config(self):
        from nexus.project_config import _DEFAULT_CONFIG
        self.assertIn("slug", _DEFAULT_CONFIG["project"])

    def test_ensure_config_includes_slug(self):
        ensure_project_config(str(self.project))
        config = load_project_config(str(self.project))
        self.assertIn("slug", config["project"])

    def test_apply_overrides_includes_slug(self):
        cfg_path = self.project / "nexus.yaml"
        cfg_path.write_text(yaml.dump({
            "schema_version": 1,
            "project": {"slug": "custom-slug"},
        }))
        entry = ProjectEntry(path=str(self.project), name="Test", slug="auto-slug")
        result = apply_project_overrides(entry)
        self.assertEqual(result.slug, "custom-slug")


if __name__ == "__main__":
    unittest.main()
