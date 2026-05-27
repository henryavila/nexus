import unittest
from pathlib import Path
from nexus import (
    APPS_YML, ENVIRONMENTS_YML,
    DATA_DIR,
)


class TestNewConstants(unittest.TestCase):
    def test_apps_yml_path(self):
        self.assertEqual(APPS_YML, DATA_DIR / "apps.yml")

    def test_environments_yml_path(self):
        self.assertEqual(ENVIRONMENTS_YML, DATA_DIR / "environments.yml")


if __name__ == "__main__":
    unittest.main()
