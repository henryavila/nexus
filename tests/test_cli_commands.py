import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from nexus.registry import ProjectEntry, add_project, load_registry, resolve_project, save_registry


class TestCmdNote(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.tmpdir.name)
        self.yml = self.data_dir / "projects.yml"
        self.json = self.data_dir / "data.json"
        self.patches = [
            patch("nexus.registry.PROJECTS_YML", self.yml),
            patch("nexus.registry.DATA_JSON", self.json),
            patch("nexus.registry.DATA_DIR", self.data_dir),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.tmpdir.cleanup()

    def test_note_updates_registry(self):
        from nexus.registry import save_registry, update_project
        entry = ProjectEntry(
            path="/tmp/test-project",
            name="test",
            description="test project",
            domain="pessoal",
            added="2026-02-25",
        )
        save_registry([entry])
        result = update_project("/tmp/test-project", note="new note")
        self.assertIsNotNone(result)
        self.assertEqual(result.note, "new note")
        loaded = load_registry()
        self.assertEqual(loaded[0].note, "new note")


class TestMoveProject(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.tmpdir.name) / "data"
        self.data_dir.mkdir()
        self.yml = self.data_dir / "projects.yml"
        self.json = self.data_dir / "data.json"
        self.patches = [
            patch("nexus.registry.PROJECTS_YML", self.yml),
            patch("nexus.registry.DATA_JSON", self.json),
            patch("nexus.registry.DATA_DIR", self.data_dir),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.tmpdir.cleanup()

    def test_move_updates_registry_path(self):
        from nexus.registry import save_registry, move_project

        old_dir = Path(self.tmpdir.name) / "old" / "MyProject"
        new_dir = Path(self.tmpdir.name) / "new" / "MyProject"
        old_dir.mkdir(parents=True)
        new_dir.mkdir(parents=True)

        entry = ProjectEntry(
            path=str(old_dir), name="MyProject", domain="pessoal", added="2026-02-27",
        )
        save_registry([entry])

        result = move_project(str(old_dir), str(new_dir))
        self.assertIsNotNone(result)
        self.assertEqual(result.path, str(new_dir.resolve()))

        entries = load_registry()
        self.assertEqual(entries[0].path, str(new_dir.resolve()))

    def test_move_nonexistent_project_returns_none(self):
        from nexus.registry import save_registry, move_project

        new_dir = Path(self.tmpdir.name) / "new"
        new_dir.mkdir()
        save_registry([])
        result = move_project("/nonexistent", str(new_dir))
        self.assertIsNone(result)

    def test_move_to_existing_path_returns_none(self):
        from nexus.registry import save_registry, move_project

        dir_a = Path(self.tmpdir.name) / "a" / "ProjA"
        dir_b = Path(self.tmpdir.name) / "b" / "ProjB"
        dir_a.mkdir(parents=True)
        dir_b.mkdir(parents=True)
        entries = [
            ProjectEntry(path=str(dir_a), name="ProjA", domain="pessoal"),
            ProjectEntry(path=str(dir_b), name="ProjB", domain="pessoal"),
        ]
        save_registry(entries)
        result = move_project(str(dir_a), str(dir_b))
        self.assertIsNone(result)


class CmdOpenIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.tmpdir.name)
        self.yml = self.data_dir / "projects.yml"
        self.json = self.data_dir / "data.json"
        self.json.write_text('{"version":"3.0","last_full_scan":null,"projects":[],"ideas":[]}')
        self.yml.write_text("projects: []\n")
        self.patches = [
            patch("nexus.registry.PROJECTS_YML", self.yml),
            patch("nexus.registry.DATA_JSON", self.json),
            patch("nexus.registry.DATA_DIR", self.data_dir),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.tmpdir.cleanup()

    def test_open_end_to_end_with_slug(self):
        """Full flow: add project -> auto-slug -> resolve by slug."""
        proj_dir = self.data_dir / "testproj"
        proj_dir.mkdir()

        entry = ProjectEntry(path=str(proj_dir), name="Test Project")
        created, result = add_project(entry)
        self.assertTrue(created)
        self.assertEqual(result.slug, "tp")  # initials (2 words)

        # Findable by slug
        found, _ = resolve_project("tp")
        self.assertIsNotNone(found)
        self.assertEqual(found.name, "Test Project")

        # Also findable by partial name
        found2, _ = resolve_project("test")
        self.assertIsNotNone(found2)
        self.assertEqual(found2.name, "Test Project")


if __name__ == "__main__":
    unittest.main()
