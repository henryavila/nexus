import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
from io import StringIO

from nexus.environment import EnvironmentEntry, save_environments


class TestCmdEnvList(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.env_yml = Path(self.tmpdir.name) / "environments.yml"
        self.patches = [
            patch("nexus.environment.ENVIRONMENTS_YML", self.env_yml),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.tmpdir.cleanup()

    @patch("sys.stdout", new_callable=StringIO)
    @patch("nexus.environment.get_current_hostname", return_value="HOST-A")
    def test_list_shows_environments(self, _, mock_stdout):
        save_environments([
            EnvironmentEntry(hostname="HOST-A", name="Desktop", location="casa", last_seen="2026-03-10"),
            EnvironmentEntry(hostname="HOST-B", name="Laptop", location="casa", last_seen="2026-03-09"),
        ])
        from nexus._legacy_main import cmd_env_list
        cmd_env_list()
        output = mock_stdout.getvalue()
        self.assertIn("Desktop", output)
        self.assertIn("Laptop", output)

    @patch("sys.stdout", new_callable=StringIO)
    def test_list_empty(self, mock_stdout):
        from nexus._legacy_main import cmd_env_list
        cmd_env_list()
        output = mock_stdout.getvalue()
        self.assertIn("nenhum", output.lower())


if __name__ == "__main__":
    unittest.main()
