import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from nexus.local_config import get_resolved_path, set_path_override, load_local_config


class TestLocalConfig(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.config_path = Path(self.tmpdir.name) / "local.yml"
        self.patch = patch("nexus.local_config.LOCAL_CONFIG_PATH", self.config_path)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.tmpdir.cleanup()

    def test_no_override_returns_original(self):
        result = get_resolved_path("/home/user/project")
        self.assertEqual(result, "/home/user/project")

    def test_override_returns_new_path(self):
        set_path_override("/home/user/project", "/other/path/project")
        result = get_resolved_path("/home/user/project")
        self.assertEqual(result, "/other/path/project")

    def test_config_persists(self):
        set_path_override("/a/b", "/c/d")
        config = load_local_config()
        self.assertIn("/a/b", config.get("path_overrides", {}))


if __name__ == "__main__":
    unittest.main()
