import unittest
from unittest.mock import patch

from nexus.cli_registry import CLI_REGISTRY, CliEntry, detect_clis


class CliRegistryTests(unittest.TestCase):
    def test_registry_has_entries(self):
        self.assertGreater(len(CLI_REGISTRY), 0)

    def test_entries_are_cli_entry(self):
        for entry in CLI_REGISTRY:
            self.assertIsInstance(entry, CliEntry)

    def test_detect_clis_filters_by_which(self):
        with patch("nexus.cli_registry.shutil.which") as mock_which:
            mock_which.side_effect = lambda cmd: "/usr/bin/claude" if cmd == "claude" else None
            result = detect_clis()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].cmd, "claude")

    def test_detect_clis_returns_empty_when_none_found(self):
        with patch("nexus.cli_registry.shutil.which", return_value=None):
            result = detect_clis()
        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
