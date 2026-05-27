import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from nexus.integrity import slug_exists, check_registry_integrity


class TestSlugExists(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.projects_yml = Path(self.tmpdir.name) / "projects.yml"
        self.apps_yml = Path(self.tmpdir.name) / "apps.yml"
        self.data_json = Path(self.tmpdir.name) / "data.json"
        self.data_dir = Path(self.tmpdir.name)
        self.patches = [
            patch("nexus.integrity.PROJECTS_YML", self.projects_yml),
            patch("nexus.integrity.APPS_YML", self.apps_yml),
            patch("nexus.registry.PROJECTS_YML", self.projects_yml),
            patch("nexus.registry.DATA_JSON", self.data_json),
            patch("nexus.registry.DATA_DIR", self.data_dir),
            patch("nexus.apps.APPS_YML", self.apps_yml),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.tmpdir.cleanup()

    def test_no_files_returns_none(self):
        self.assertIsNone(slug_exists("anything"))

    def test_found_in_projects(self):
        from nexus.registry import save_registry, ProjectEntry
        save_registry([ProjectEntry(path="/tmp/x", name="Test", slug="test")])
        self.assertEqual(slug_exists("test"), "project")

    def test_found_in_apps(self):
        from nexus.apps import save_apps, AppEntry
        save_apps([AppEntry(name="MyApp", slug="myapp")])
        self.assertEqual(slug_exists("myapp"), "app")

    def test_not_found(self):
        self.assertIsNone(slug_exists("nonexistent"))


class TestCheckRegistryIntegrity(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.projects_yml = Path(self.tmpdir.name) / "projects.yml"
        self.apps_yml = Path(self.tmpdir.name) / "apps.yml"
        self.data_json = Path(self.tmpdir.name) / "data.json"
        self.data_dir = Path(self.tmpdir.name)
        self.patches = [
            patch("nexus.integrity.PROJECTS_YML", self.projects_yml),
            patch("nexus.integrity.APPS_YML", self.apps_yml),
            patch("nexus.registry.PROJECTS_YML", self.projects_yml),
            patch("nexus.registry.DATA_JSON", self.data_json),
            patch("nexus.registry.DATA_DIR", self.data_dir),
            patch("nexus.apps.APPS_YML", self.apps_yml),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.tmpdir.cleanup()

    def test_no_duplicates_no_change(self):
        from nexus.registry import save_registry, ProjectEntry
        save_registry([ProjectEntry(path="/tmp/a", name="A", slug="a")])
        check_registry_integrity()
        from nexus.registry import load_registry
        self.assertEqual(len(load_registry()), 1)

    def test_duplicate_slug_app_wins(self):
        from nexus.registry import save_registry, ProjectEntry, load_registry
        from nexus.apps import save_apps, AppEntry, load_apps
        save_registry([ProjectEntry(path="/tmp/x", name="X", slug="dupe")])
        save_apps([AppEntry(name="X App", slug="dupe")])
        check_registry_integrity()
        projects = load_registry()
        apps = load_apps()
        self.assertEqual(len(apps), 1)
        project_slugs = [p.slug for p in projects]
        self.assertNotIn("dupe", project_slugs)


if __name__ == "__main__":
    unittest.main()
