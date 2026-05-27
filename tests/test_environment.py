import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
from nexus.environment import EnvironmentEntry, load_environments, save_environments, find_environment


class TestEnvironmentEntry(unittest.TestCase):
    def test_defaults(self):
        e = EnvironmentEntry(hostname="TEST-PC", name="Test PC", location="casa")
        self.assertEqual(e.hostname, "TEST-PC")
        self.assertEqual(e.name, "Test PC")
        self.assertEqual(e.location, "casa")
        self.assertEqual(e.last_seen, "")
        self.assertEqual(e.paths, {})
        self.assertEqual(e.absent, [])


class TestLoadSaveEnvironments(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.yml = Path(self.tmpdir.name) / "environments.yml"
        self.patch = patch("nexus.environment.ENVIRONMENTS_YML", self.yml)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.tmpdir.cleanup()

    def test_load_empty(self):
        result = load_environments()
        self.assertEqual(result, [])

    def test_load_nonexistent(self):
        result = load_environments()
        self.assertEqual(result, [])

    def test_roundtrip(self):
        entries = [
            EnvironmentEntry(
                hostname="DESK-123",
                name="Desktop Casa",
                location="casa",
                last_seen="2026-03-10",
                paths={"nexus": "/home/user/nexus", "arch": "/home/user/arch"},
                absent=["dragon-heir"],
            )
        ]
        save_environments(entries)
        loaded = load_environments()
        self.assertEqual(len(loaded), 1)
        e = loaded[0]
        self.assertEqual(e.hostname, "DESK-123")
        self.assertEqual(e.name, "Desktop Casa")
        self.assertEqual(e.location, "casa")
        self.assertEqual(e.paths, {"nexus": "/home/user/nexus", "arch": "/home/user/arch"})
        self.assertEqual(e.absent, ["dragon-heir"])

    def test_save_omits_empty_optional_fields(self):
        entries = [EnvironmentEntry(hostname="H", name="N", location="L")]
        save_environments(entries)
        text = self.yml.read_text()
        self.assertNotIn("absent", text)

    def test_multiple_environments(self):
        entries = [
            EnvironmentEntry(hostname="A", name="PC A", location="casa"),
            EnvironmentEntry(hostname="B", name="PC B", location="trabalho"),
        ]
        save_environments(entries)
        loaded = load_environments()
        self.assertEqual(len(loaded), 2)
        self.assertEqual(loaded[0].hostname, "A")
        self.assertEqual(loaded[1].hostname, "B")


class TestEnvironmentDetection(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.yml = Path(self.tmpdir.name) / "environments.yml"
        self.patch = patch("nexus.environment.ENVIRONMENTS_YML", self.yml)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.tmpdir.cleanup()

    @patch("nexus.environment.get_current_hostname", return_value="TEST-HOST")
    def test_detect_new_environment(self, _):
        env = find_environment()
        self.assertIsNone(env)

    @patch("nexus.environment.get_current_hostname", return_value="KNOWN-HOST")
    def test_detect_known_environment(self, _):
        save_environments([
            EnvironmentEntry(hostname="KNOWN-HOST", name="My PC", location="casa")
        ])
        env = find_environment()
        self.assertIsNotNone(env)
        self.assertEqual(env.name, "My PC")

    @patch("nexus.environment.get_current_hostname", return_value="NEW-HOST")
    def test_register_environment(self, _):
        from nexus.environment import register_environment
        env = register_environment("Novo PC", "casa")
        self.assertEqual(env.hostname, "NEW-HOST")
        self.assertEqual(env.name, "Novo PC")
        # Persisted
        loaded = load_environments()
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0].hostname, "NEW-HOST")

    @patch("nexus.environment.get_current_hostname", return_value="EXIST")
    def test_register_existing_returns_existing(self, _):
        from nexus.environment import register_environment
        save_environments([
            EnvironmentEntry(hostname="EXIST", name="Old", location="x")
        ])
        env = register_environment("New Name", "y")
        self.assertEqual(env.name, "Old")  # Not overwritten

    def test_set_path(self):
        from nexus.environment import set_environment_path
        save_environments([
            EnvironmentEntry(hostname="H", name="N", location="L")
        ])
        set_environment_path("H", "nexus", "/home/user/nexus")
        loaded = load_environments()
        self.assertEqual(loaded[0].paths["nexus"], "/home/user/nexus")

    def test_mark_absent(self):
        from nexus.environment import mark_absent
        save_environments([
            EnvironmentEntry(hostname="H", name="N", location="L")
        ])
        mark_absent("H", "arch")
        loaded = load_environments()
        self.assertIn("arch", loaded[0].absent)

    def test_mark_absent_idempotent(self):
        from nexus.environment import mark_absent
        save_environments([
            EnvironmentEntry(hostname="H", name="N", location="L", absent=["arch"])
        ])
        mark_absent("H", "arch")
        loaded = load_environments()
        self.assertEqual(loaded[0].absent.count("arch"), 1)


class TestNonInteractiveOnboarding(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.yml = Path(self.tmpdir.name) / "environments.yml"
        self.patch = patch("nexus.environment.ENVIRONMENTS_YML", self.yml)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.tmpdir.cleanup()

    @patch("nexus.environment.get_current_hostname", return_value="BG-HOST")
    @patch("sys.stdin")
    def test_non_interactive_registers_with_hostname(self, mock_stdin, _):
        from nexus.environment import register_environment_non_interactive
        mock_stdin.isatty.return_value = False
        env = register_environment_non_interactive()
        self.assertEqual(env.hostname, "BG-HOST")
        self.assertEqual(env.name, "BG-HOST")
        self.assertEqual(env.location, "unknown")


class TestResolvePathForEntry(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.yml = Path(self.tmpdir.name) / "environments.yml"
        self.patch = patch("nexus.environment.ENVIRONMENTS_YML", self.yml)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.tmpdir.cleanup()

    @patch("nexus.environment.get_current_hostname", return_value="HOST")
    def test_env_path_takes_priority(self, _):
        from nexus.environment import resolve_path_for_entry
        save_environments([EnvironmentEntry(hostname="HOST", name="H", location="L",
                             paths={"nexus": "/env/path"})])
        self.assertEqual(resolve_path_for_entry("nexus", "/legacy"), "/env/path")

    @patch("nexus.environment.get_current_hostname", return_value="HOST")
    def test_falls_back_to_entry_path(self, _):
        from nexus.environment import resolve_path_for_entry
        save_environments([EnvironmentEntry(hostname="HOST", name="H", location="L")])
        self.assertEqual(resolve_path_for_entry("nexus", "/legacy"), "/legacy")

    def test_returns_none_when_nothing(self):
        from nexus.environment import resolve_path_for_entry
        self.assertIsNone(resolve_path_for_entry("nexus", None))

    @patch("nexus.environment.get_current_hostname", return_value="HOST")
    def test_env_path_with_empty_slug(self, _):
        from nexus.environment import resolve_path_for_entry
        save_environments([EnvironmentEntry(hostname="HOST", name="H", location="L",
                             paths={"nexus": "/env/path"})])
        # Empty slug should fall back to entry_path
        self.assertEqual(resolve_path_for_entry("", "/legacy"), "/legacy")

    @patch("nexus.environment.get_current_hostname", return_value="OTHER")
    def test_no_matching_environment(self, _):
        from nexus.environment import resolve_path_for_entry
        save_environments([EnvironmentEntry(hostname="HOST", name="H", location="L",
                             paths={"nexus": "/env/path"})])
        # Different hostname means no environment found, falls back to entry_path
        self.assertEqual(resolve_path_for_entry("nexus", "/legacy"), "/legacy")


class TestUpdateEnvironment(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.env_yml = Path(self.tmpdir.name) / "environments.yml"
        self.patcher = patch("nexus.environment.ENVIRONMENTS_YML", self.env_yml)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        self.tmpdir.cleanup()

    def test_update_name(self):
        from nexus.environment import update_environment
        save_environments([EnvironmentEntry(hostname="H", name="Old", location="L")])
        self.assertTrue(update_environment("H", name="New"))
        envs = load_environments()
        self.assertEqual(envs[0].name, "New")
        self.assertEqual(envs[0].location, "L")

    def test_update_location(self):
        from nexus.environment import update_environment
        save_environments([EnvironmentEntry(hostname="H", name="N", location="Old")])
        self.assertTrue(update_environment("H", location="New"))
        envs = load_environments()
        self.assertEqual(envs[0].location, "New")

    def test_update_both(self):
        from nexus.environment import update_environment
        save_environments([EnvironmentEntry(hostname="H", name="O", location="O")])
        self.assertTrue(update_environment("H", name="N", location="L"))
        envs = load_environments()
        self.assertEqual(envs[0].name, "N")
        self.assertEqual(envs[0].location, "L")

    def test_update_not_found(self):
        from nexus.environment import update_environment
        save_environments([EnvironmentEntry(hostname="H", name="N", location="L")])
        self.assertFalse(update_environment("MISSING", name="X"))


if __name__ == "__main__":
    unittest.main()
