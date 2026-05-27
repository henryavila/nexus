import json
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from nexus.ideas import (
    IdeaEntry, add_idea, ensure_ideas_bootstrap, load_ideas, remove_idea,
    resolve_idea, save_ideas, sort_ideas, update_idea, _update_ideas_in_data_json,
)


class TestIdeaRegistry(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.tmpdir.name)
        self.ideas_yml = self.data_dir / "ideas.yml"
        self.data_json = self.data_dir / "data.json"
        self.lock_file = self.data_dir / ".nexus.lock"
        self.projects_yml = self.data_dir / "projects.yml"

        self.patches = [
            patch("nexus.ideas.IDEAS_YML", self.ideas_yml),
            patch("nexus.ideas.DATA_JSON", self.data_json),
            patch("nexus.ideas.LOCK_FILE", self.lock_file),
            # Patches for registry (used by _update_ideas_in_data_json → ensure_bootstrap)
            patch("nexus.registry.PROJECTS_YML", self.projects_yml),
            patch("nexus.registry.DATA_JSON", self.data_json),
            patch("nexus.registry.DATA_DIR", self.data_dir),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.tmpdir.cleanup()

    def test_ensure_bootstrap_creates_file(self):
        self.assertFalse(self.ideas_yml.exists())
        ensure_ideas_bootstrap()
        self.assertTrue(self.ideas_yml.exists())
        content = self.ideas_yml.read_text()
        self.assertIn("ideas:", content)

    def test_add_idea_assigns_id(self):
        entry = IdeaEntry(title="Test Idea")
        result = add_idea(entry)
        self.assertEqual(len(result.id), 8)
        self.assertTrue(all(c in "0123456789abcdef" for c in result.id))

    def test_add_multiple_ideas_unique_ids(self):
        ids = set()
        for i in range(3):
            result = add_idea(IdeaEntry(title=f"Idea {i}"))
            ids.add(result.id)
        self.assertEqual(len(ids), 3)

    def test_load_save_round_trip(self):
        entry = IdeaEntry(
            title="Bot de resumo",
            description="Resume reunioes com IA",
            domain="trabalho",
            priority="high",
            references=["https://example.com"],
            notes="Usar Whisper API",
        )
        result = add_idea(entry)
        loaded = load_ideas()
        self.assertEqual(len(loaded), 1)
        e = loaded[0]
        self.assertEqual(e.id, result.id)
        self.assertEqual(e.title, "Bot de resumo")
        self.assertEqual(e.description, "Resume reunioes com IA")
        self.assertEqual(e.domain, "trabalho")
        self.assertEqual(e.priority, "high")
        self.assertEqual(e.references, ["https://example.com"])
        self.assertEqual(e.notes, "Usar Whisper API")

    def test_update_idea(self):
        result = add_idea(IdeaEntry(title="Original"))
        update_idea(result.id, title="Updated")
        loaded = load_ideas()
        self.assertEqual(loaded[0].title, "Updated")

    def test_update_idea_nonexistent(self):
        result = update_idea("nonexistent", title="nope")
        self.assertIsNone(result)

    def test_remove_idea(self):
        result = add_idea(IdeaEntry(title="To Remove"))
        removed = remove_idea(result.id)
        self.assertIsNotNone(removed)
        self.assertEqual(removed.title, "To Remove")
        loaded = load_ideas()
        self.assertEqual(len(loaded), 0)

    def test_remove_idea_nonexistent(self):
        result = remove_idea("nonexistent")
        self.assertIsNone(result)

    def test_resolve_idea_by_id(self):
        r1 = add_idea(IdeaEntry(title="Alpha"))
        r2 = add_idea(IdeaEntry(title="Beta"))
        matched, ambiguous = resolve_idea(r2.id)
        self.assertEqual(matched.title, "Beta")
        self.assertEqual(ambiguous, [])

    def test_resolve_idea_by_title(self):
        add_idea(IdeaEntry(title="Bot de resumo"))
        matched, ambiguous = resolve_idea("Bot de resumo")
        self.assertIsNotNone(matched)
        self.assertEqual(matched.title, "Bot de resumo")

    def test_resolve_idea_partial_match(self):
        add_idea(IdeaEntry(title="Bot de resumo"))
        matched, ambiguous = resolve_idea("resumo")
        self.assertIsNotNone(matched)
        self.assertEqual(matched.title, "Bot de resumo")

    def test_resolve_idea_id_wins_over_title(self):
        r1 = add_idea(IdeaEntry(title="First"))
        # Create another idea with title matching first idea's id
        r2 = add_idea(IdeaEntry(title=r1.id))
        matched, _ = resolve_idea(r1.id)
        # ID match should win
        self.assertEqual(matched.title, "First")

    def test_sort_ideas_by_priority(self):
        add_idea(IdeaEntry(title="Low", priority="low", created="2026-01-01"))
        add_idea(IdeaEntry(title="High", priority="high", created="2026-01-01"))
        add_idea(IdeaEntry(title="Medium", priority="medium", created="2026-01-01"))
        ideas = load_ideas()
        sorted_ideas = sort_ideas(ideas)
        self.assertEqual(sorted_ideas[0].priority, "high")
        self.assertEqual(sorted_ideas[1].priority, "medium")
        self.assertEqual(sorted_ideas[2].priority, "low")

    def test_sort_ideas_tiebreak_by_created(self):
        add_idea(IdeaEntry(title="Older", priority="high", created="2026-01-01"))
        add_idea(IdeaEntry(title="Newer", priority="high", created="2026-03-01"))
        ideas = load_ideas()
        sorted_ideas = sort_ideas(ideas)
        # Newest first within same priority
        self.assertEqual(sorted_ideas[0].title, "Newer")
        self.assertEqual(sorted_ideas[1].title, "Older")

    def test_save_preserves_empty_lists(self):
        entry = IdeaEntry(title="With Empty Tags")
        add_idea(entry)
        loaded = load_ideas()

    def test_save_omits_none_fields(self):
        entry = IdeaEntry(title="No Tags")
        add_idea(entry)
        # Read raw YAML to verify key absence
        import yaml
        raw = yaml.safe_load(self.ideas_yml.read_text())
        item = raw["ideas"][0]
        self.assertNotIn("tags", item)

    def test_update_ideas_in_data_json(self):
        add_idea(IdeaEntry(title="Idea 1", priority="high"))
        add_idea(IdeaEntry(title="Idea 2", priority="low"))
        _update_ideas_in_data_json()
        data = json.loads(self.data_json.read_text())
        self.assertIn("ideas", data)
        self.assertEqual(len(data["ideas"]), 2)
        # Should be sorted: high first
        self.assertEqual(data["ideas"][0]["title"], "Idea 1")
        self.assertEqual(data["version"], "3.0")
        # projects key should exist
        self.assertIn("projects", data)

    def test_update_ideas_creates_data_json_if_missing(self):
        self.assertFalse(self.data_json.exists())
        add_idea(IdeaEntry(title="First Idea"))
        _update_ideas_in_data_json()
        self.assertTrue(self.data_json.exists())
        data = json.loads(self.data_json.read_text())
        self.assertEqual(len(data["ideas"]), 1)
        self.assertIn("projects", data)

    def test_update_ideas_preserves_projects(self):
        # Write data.json with projects first
        data = {"version": "2.0", "projects": [{"name": "test"}]}
        self.data_json.write_text(json.dumps(data))
        add_idea(IdeaEntry(title="New Idea"))
        _update_ideas_in_data_json()
        loaded = json.loads(self.data_json.read_text())
        self.assertEqual(len(loaded["projects"]), 1)
        self.assertEqual(loaded["projects"][0]["name"], "test")
        self.assertEqual(len(loaded["ideas"]), 1)


if __name__ == "__main__":
    unittest.main()
