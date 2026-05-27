import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from nexus.skills import SkillEntry, load_skills, save_skill_entry, resolve_skill


class TestSkillEntry(unittest.TestCase):
    def test_defaults(self):
        s = SkillEntry(title="superpowers", slug="superpowers")
        self.assertEqual(s.scope, "global")
        self.assertIsNone(s.url)
        self.assertEqual(s.content, "")


class TestSkillPersistence(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.skills_dir = Path(self.tmpdir.name) / "skills"
        self.patch = patch("nexus.skills.SKILLS_DIR", self.skills_dir)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.tmpdir.cleanup()

    def test_load_empty_dir(self):
        self.skills_dir.mkdir()
        self.assertEqual(load_skills(), [])

    def test_load_no_dir(self):
        self.assertEqual(load_skills(), [])

    def test_save_creates_dir(self):
        save_skill_entry(SkillEntry(title="test", slug="test"))
        self.assertTrue(self.skills_dir.exists())

    def test_roundtrip(self):
        entry = SkillEntry(
            title="superpowers",
            slug="superpowers",
            scope="global",
            url="https://github.com/example",
            added="2026-01-15",
            content="## Dicas\n- Use brainstorming first\n",
        )
        save_skill_entry(entry)
        loaded = load_skills()
        self.assertEqual(len(loaded), 1)
        s = loaded[0]
        self.assertEqual(s.title, "superpowers")
        self.assertEqual(s.slug, "superpowers")
        self.assertEqual(s.scope, "global")
        self.assertEqual(s.url, "https://github.com/example")
        self.assertIn("brainstorming", s.content)

    def test_frontmatter_format(self):
        save_skill_entry(SkillEntry(
            title="bmad", slug="bmad", scope="repo",
            url="https://bmad.dev", added="2026-02-01",
        ))
        text = (self.skills_dir / "bmad.md").read_text()
        self.assertIn("---", text)
        self.assertIn("title: bmad", text)
        self.assertIn("scope: repo", text)

    def test_resolve_by_slug(self):
        save_skill_entry(SkillEntry(title="superpowers", slug="superpowers"))
        entry, _ = resolve_skill("superpowers")
        self.assertIsNotNone(entry)

    def test_resolve_partial(self):
        save_skill_entry(SkillEntry(title="superpowers", slug="superpowers"))
        entry, _ = resolve_skill("super")
        self.assertIsNotNone(entry)

    def test_omits_none_url(self):
        save_skill_entry(SkillEntry(title="test", slug="test"))
        text = (self.skills_dir / "test.md").read_text()
        self.assertNotIn("url", text)


class TestSkillDetection(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.plugins_dir = Path(self.tmpdir.name) / "plugins" / "cache"
        self.skills_dir = Path(self.tmpdir.name) / "data" / "skills"
        self.patches = [
            patch("nexus.skills.SKILLS_DIR", self.skills_dir),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.tmpdir.cleanup()

    def test_detect_global_skills(self):
        from nexus.skills import detect_global_skills
        sp = self.plugins_dir / "claude-plugins-official" / "superpowers" / "5.0.0"
        sp.mkdir(parents=True)
        (sp / "skills").mkdir()
        result = detect_global_skills(self.plugins_dir.parent)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["slug"], "superpowers")
        self.assertEqual(result[0]["version"], "5.0.0")

    def test_detect_global_multiple_versions_picks_latest(self):
        from nexus.skills import detect_global_skills
        base = self.plugins_dir / "org" / "tool"
        (base / "1.0.0").mkdir(parents=True)
        (base / "2.0.0").mkdir(parents=True)
        result = detect_global_skills(self.plugins_dir.parent)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["version"], "2.0.0")

    def test_detect_repo_skills(self):
        from nexus.skills import detect_repo_skills
        repo = Path(self.tmpdir.name) / "project"
        (repo / ".bmad").mkdir(parents=True)
        result = detect_repo_skills(str(repo))
        self.assertTrue(any(s["slug"] == "bmad" for s in result))

    def test_detect_repo_skills_empty(self):
        from nexus.skills import detect_repo_skills
        repo = Path(self.tmpdir.name) / "empty"
        repo.mkdir()
        result = detect_repo_skills(str(repo))
        self.assertEqual(result, [])


class TestVersionKey(unittest.TestCase):
    def test_semver_comparison(self):
        from nexus.skills import version_key
        self.assertGreater(version_key("10.0.0"), version_key("9.0.0"))
        self.assertGreater(version_key("2.1.0"), version_key("2.0.9"))
        self.assertEqual(version_key("1.0.0"), (1, 0, 0))

    def test_invalid_version(self):
        from nexus.skills import version_key
        self.assertEqual(version_key("unknown"), (0,))
        self.assertEqual(version_key(""), (0,))



if __name__ == "__main__":
    unittest.main()
