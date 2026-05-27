import unittest
from pathlib import Path

from nexus.registry import normalize_path


def _onedrive_available() -> bool:
    try:
        return Path("/mnt/e/OneDrive").exists()
    except OSError:
        return False


class TestNormalizePathCaseResolution(unittest.TestCase):
    """normalize_path must resolve to actual filesystem case.

    On WSL, /mnt/ mounts are case-insensitive (NTFS). A user can type
    '/mnt/e/Onedrive' but the real directory is 'OneDrive'. normalize_path
    must return the real case so encoded paths match Claude Code's dirs.
    """

    @unittest.skipUnless(
        _onedrive_available(),
        "WSL OneDrive mount not available",
    )
    def test_resolves_case_on_case_insensitive_mount(self):
        result = normalize_path("/mnt/e/Onedrive")
        self.assertIn("OneDrive", result)
        self.assertNotIn("Onedrive", result)

    @unittest.skipUnless(
        _onedrive_available(),
        "WSL OneDrive mount not available",
    )
    def test_resolves_case_deep_path(self):
        # Use a known subdir under OneDrive
        real_children = list(Path("/mnt/e/OneDrive").iterdir())
        if not real_children:
            self.skipTest("OneDrive is empty")
        child = real_children[0]
        wrong_case = f"/mnt/e/onedrive/{child.name.lower()}"
        result = normalize_path(wrong_case)
        self.assertEqual(result, str(Path("/mnt/e/OneDrive") / child.name))

    def test_preserves_correct_case(self):
        """Paths already with correct case should not be altered."""
        # Use /tmp which exists on all Linux/macOS systems.
        # On macOS, /tmp is a symlink to /private/tmp, so resolve() is needed.
        result = normalize_path("/tmp")
        self.assertEqual(result, str(Path("/tmp").resolve()))

    def test_nonexistent_path_returned_as_is(self):
        result = normalize_path("/nonexistent/path/here")
        self.assertEqual(result, "/nonexistent/path/here")


if __name__ == "__main__":
    unittest.main()
