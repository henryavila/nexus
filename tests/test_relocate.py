import unittest
import tempfile
from pathlib import Path

from nexus.relocate import find_moved_project


class TestFindMovedProject(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_finds_project_in_parent_sibling(self):
        """Project moved from /root/old/MyProject to /root/new/MyProject."""
        old_parent = self.root / "old"
        old_parent.mkdir()
        new_location = self.root / "new" / "MyProject"
        new_location.mkdir(parents=True)
        (new_location / ".git").mkdir()

        old_path = str(old_parent / "MyProject")
        candidates = find_moved_project(old_path)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0], str(new_location))

    def test_finds_project_in_grandparent(self):
        """Project moved 2 levels up from original location."""
        deep = self.root / "a" / "b" / "c"
        deep.mkdir(parents=True)
        new_location = self.root / "a" / "x" / "MyProject"
        new_location.mkdir(parents=True)
        (new_location / ".git").mkdir()

        old_path = str(deep / "MyProject")
        candidates = find_moved_project(old_path)
        self.assertIn(str(new_location), candidates)

    def test_returns_empty_when_not_found(self):
        old_path = str(self.root / "nonexistent" / "MyProject")
        candidates = find_moved_project(old_path)
        self.assertEqual(candidates, [])

    def test_skips_excluded_dirs(self):
        """Should not search inside node_modules, .git, etc."""
        parent = self.root / "parent"
        parent.mkdir()
        hidden = parent / "node_modules" / "MyProject"
        hidden.mkdir(parents=True)

        old_path = str(self.root / "other" / "MyProject")
        candidates = find_moved_project(old_path)
        self.assertNotIn(str(hidden), candidates)

    def test_validates_with_nexus_yaml(self):
        """Prefers candidate that has nexus.yaml."""
        parent = self.root / "parent"
        # Two folders with same basename
        loc_a = parent / "sub1" / "MyProject"
        loc_a.mkdir(parents=True)
        loc_b = parent / "sub2" / "MyProject"
        loc_b.mkdir(parents=True)
        (loc_b / "nexus.yaml").write_text("schema_version: 1\n")

        old_path = str(parent / "old" / "MyProject")
        candidates = find_moved_project(old_path)
        # The one with nexus.yaml should be first
        self.assertEqual(candidates[0], str(loc_b))

    def test_parent_does_not_exist(self):
        """If parent dir doesn't exist (drive unmounted), returns empty."""
        old_path = "/mnt/nonexistent/drive/MyProject"
        candidates = find_moved_project(old_path)
        self.assertEqual(candidates, [])


if __name__ == "__main__":
    unittest.main()
