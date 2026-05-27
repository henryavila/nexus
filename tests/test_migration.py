# tests/test_migration.py
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch


class TestMigrationV2ToV3(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.projects_yml = Path(self.tmpdir.name) / "projects.yml"
        self.env_yml = Path(self.tmpdir.name) / "environments.yml"
        self.data_json = Path(self.tmpdir.name) / "data.json"
        self.data_dir = Path(self.tmpdir.name)
        self.patches = [
            patch("nexus.registry.PROJECTS_YML", self.projects_yml),
            patch("nexus.registry.DATA_JSON", self.data_json),
            patch("nexus.registry.DATA_DIR", self.data_dir),
            patch("nexus.environment.ENVIRONMENTS_YML", self.env_yml),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.tmpdir.cleanup()

    @patch("nexus.environment.get_current_hostname", return_value="MY-HOST")
    def test_migrate_paths_to_environment(self, _):
        from nexus.registry import save_registry, ProjectEntry
        save_registry([
            ProjectEntry(name="nexus", slug="nexus", path="/home/user/nexus"),
            ProjectEntry(name="arch", slug="arch", path="/home/user/arch"),
        ])
        from nexus.environment import migrate_paths_from_registry
        migrate_paths_from_registry("My PC", "casa")
        from nexus.environment import load_environments
        envs = load_environments()
        self.assertEqual(len(envs), 1)
        self.assertEqual(envs[0].paths["nexus"], "/home/user/nexus")
        self.assertEqual(envs[0].paths["arch"], "/home/user/arch")

    @patch("nexus.environment.get_current_hostname", return_value="EXIST")
    def test_migrate_idempotent(self, _):
        from nexus.environment import save_environments, EnvironmentEntry, migrate_paths_from_registry
        save_environments([EnvironmentEntry(hostname="EXIST", name="Old", location="x")])
        env = migrate_paths_from_registry("New", "y")
        self.assertEqual(env.name, "Old")  # Not overwritten


if __name__ == "__main__":
    unittest.main()
