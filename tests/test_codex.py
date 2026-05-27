import json
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from nexus.codex import (
    CodexEntry, _parse_frontmatter, _render_frontmatter, load_codex,
    save_codex_entry, remove_codex_entry, resolve_codex, sort_codex,
    _update_codex_in_data_json, _codex_to_dict,
)


class TestCodexFrontmatter(unittest.TestCase):
    def test_parse_frontmatter_basic(self):
        text = "---\ntitle: Test\nkind: guia\ndomain: pessoal\n---\n\nHello world"
        meta, content = _parse_frontmatter(text)
        self.assertEqual(meta["title"], "Test")
        self.assertEqual(meta["kind"], "guia")
        self.assertEqual(meta["domain"], "pessoal")
        self.assertEqual(content, "Hello world")

    def test_parse_frontmatter_no_frontmatter(self):
        text = "Just plain text"
        meta, content = _parse_frontmatter(text)
        self.assertEqual(meta, {})
        self.assertEqual(content, "Just plain text")

    def test_parse_frontmatter_legacy_category(self):
        """Loading legacy frontmatter with category should map to kind."""
        text = "---\ntitle: Test\ncategory: guia\n---\n\nContent"
        meta, content = _parse_frontmatter(text)
        self.assertEqual(meta.get("category"), "guia")

    def test_render_frontmatter_round_trip(self):
        entry = CodexEntry(
            slug="test",
            title="Test Entry",
            kind="guia",
            domain="tech",
            order=5,
            created="2026-03-09",
            updated="2026-03-09",
            content="## Section\n\nParagraph here.",
        )
        rendered = _render_frontmatter(entry)
        meta, content = _parse_frontmatter(rendered)
        self.assertEqual(meta["title"], "Test Entry")
        self.assertEqual(meta["kind"], "guia")
        self.assertEqual(meta["domain"], "tech")
        self.assertEqual(meta["order"], 5)
        self.assertIn("## Section", content)

    def test_render_frontmatter_omits_none(self):
        entry = CodexEntry(slug="test", title="Test", order=None)
        rendered = _render_frontmatter(entry)
        self.assertNotIn("order:", rendered)


class TestCodexCRUD(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.tmpdir.name)
        self.codex_dir = self.data_dir / "codex"
        self.codex_dir.mkdir(parents=True)
        self.data_json = self.data_dir / "data.json"
        self.lock_file = self.data_dir / ".nexus.lock"
        self.projects_yml = self.data_dir / "projects.yml"

        self.patches = [
            patch("nexus.codex.CODEX_DIR", self.codex_dir),
            patch("nexus.codex.DATA_JSON", self.data_json),
            patch("nexus.codex.LOCK_FILE", self.lock_file),
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

    def _create_entry(self, slug="test-entry", title="Test Entry", **kwargs):
        entry = CodexEntry(slug=slug, title=title, **kwargs)
        save_codex_entry(entry)
        return entry

    def test_save_creates_file(self):
        self._create_entry()
        path = self.codex_dir / "test-entry.md"
        self.assertTrue(path.exists())
        content = path.read_text()
        self.assertIn("title: Test Entry", content)

    def test_load_reads_all_entries(self):
        self._create_entry(slug="a", title="Alpha")
        self._create_entry(slug="b", title="Beta")
        entries = load_codex()
        self.assertEqual(len(entries), 2)
        titles = {e.title for e in entries}
        self.assertEqual(titles, {"Alpha", "Beta"})

    def test_load_empty_dir(self):
        entries = load_codex()
        self.assertEqual(entries, [])

    def test_save_load_round_trip(self):
        self._create_entry(
            slug="guia",
            title="Guia Completo",
            kind="guia",
            domain="tech",
            order=10,
            created="2026-03-09",
            updated="2026-03-09",
            content="## Section\n\nContent here.",
        )
        entries = load_codex()
        self.assertEqual(len(entries), 1)
        e = entries[0]
        self.assertEqual(e.slug, "guia")
        self.assertEqual(e.title, "Guia Completo")
        self.assertEqual(e.kind, "guia")
        self.assertEqual(e.domain, "tech")
        self.assertEqual(e.order, 10)
        self.assertIn("## Section", e.content)

    def test_save_generates_slug_from_title(self):
        entry = CodexEntry(title="Meu Guia de Teste")
        save_codex_entry(entry)
        self.assertEqual(entry.slug, "meu-guia-de-teste")
        path = self.codex_dir / "meu-guia-de-teste.md"
        self.assertTrue(path.exists())

    def test_remove_existing(self):
        self._create_entry(slug="to-remove", title="Remove Me")
        removed = remove_codex_entry("to-remove")
        self.assertIsNotNone(removed)
        self.assertEqual(removed.title, "Remove Me")
        self.assertFalse((self.codex_dir / "to-remove.md").exists())

    def test_remove_nonexistent(self):
        result = remove_codex_entry("nonexistent")
        self.assertIsNone(result)

    def test_resolve_by_slug(self):
        self._create_entry(slug="my-guide", title="My Guide")
        self._create_entry(slug="other", title="Other")
        matched, ambiguous = resolve_codex("my-guide")
        self.assertIsNotNone(matched)
        self.assertEqual(matched.slug, "my-guide")
        self.assertEqual(ambiguous, [])

    def test_resolve_by_title_exact(self):
        self._create_entry(slug="a", title="Alpha Guide")
        matched, ambiguous = resolve_codex("Alpha Guide")
        self.assertIsNotNone(matched)
        self.assertEqual(matched.title, "Alpha Guide")

    def test_resolve_by_title_partial(self):
        self._create_entry(slug="a", title="Alpha Guide")
        matched, ambiguous = resolve_codex("alpha")
        self.assertIsNotNone(matched)
        self.assertEqual(matched.title, "Alpha Guide")

    def test_resolve_ambiguous(self):
        self._create_entry(slug="a", title="Alpha Guide")
        self._create_entry(slug="b", title="Alpha Manual")
        matched, ambiguous = resolve_codex("alpha")
        self.assertIsNone(matched)
        self.assertEqual(len(ambiguous), 2)

    def test_resolve_not_found(self):
        matched, ambiguous = resolve_codex("nonexistent")
        self.assertIsNone(matched)
        self.assertEqual(ambiguous, [])

    def test_resolve_empty_query(self):
        matched, ambiguous = resolve_codex("")
        self.assertIsNone(matched)
        self.assertEqual(ambiguous, [])

    def test_sort_by_order_then_title(self):
        self._create_entry(slug="b", title="Beta", order=20)
        self._create_entry(slug="a", title="Alpha", order=10)
        self._create_entry(slug="c", title="Charlie")  # no order = last
        entries = load_codex()
        sorted_entries = sort_codex(entries)
        self.assertEqual(sorted_entries[0].title, "Alpha")
        self.assertEqual(sorted_entries[1].title, "Beta")
        self.assertEqual(sorted_entries[2].title, "Charlie")

    def test_sort_no_order_alphabetical(self):
        self._create_entry(slug="z", title="Zulu")
        self._create_entry(slug="a", title="Alpha")
        entries = load_codex()
        sorted_entries = sort_codex(entries)
        self.assertEqual(sorted_entries[0].title, "Alpha")
        self.assertEqual(sorted_entries[1].title, "Zulu")

    def test_codex_to_dict(self):
        entry = CodexEntry(
            slug="test", title="Test", kind="guia", domain="pessoal",
            order=5, created="2026-01-01",
            updated="2026-01-01", content="Hello",
        )
        d = _codex_to_dict(entry)
        self.assertEqual(d["slug"], "test")
        self.assertEqual(d["title"], "Test")
        self.assertEqual(d["kind"], "guia")
        self.assertEqual(d["domain"], "pessoal")
        self.assertEqual(d["order"], 5)
        self.assertEqual(d["content"], "Hello")

    def test_codex_to_dict_omits_none(self):
        entry = CodexEntry(slug="test", title="Test", order=None)
        d = _codex_to_dict(entry)
        self.assertNotIn("order", d)

    def test_update_codex_in_data_json(self):
        self._create_entry(slug="a", title="Alpha", order=1)
        self._create_entry(slug="b", title="Beta", order=2)
        _update_codex_in_data_json()
        data = json.loads(self.data_json.read_text())
        self.assertIn("codex", data)
        self.assertEqual(len(data["codex"]), 2)
        self.assertEqual(data["codex"][0]["title"], "Alpha")
        self.assertEqual(data["version"], "3.0")

    def test_update_codex_creates_data_json_if_missing(self):
        self.assertFalse(self.data_json.exists())
        self._create_entry(slug="first", title="First")
        _update_codex_in_data_json()
        self.assertTrue(self.data_json.exists())
        data = json.loads(self.data_json.read_text())
        self.assertEqual(len(data["codex"]), 1)

    def test_update_codex_preserves_projects(self):
        data = {"version": "2.0", "projects": [{"name": "test"}]}
        self.data_json.write_text(json.dumps(data))
        self._create_entry(slug="new", title="New Entry")
        _update_codex_in_data_json()
        loaded = json.loads(self.data_json.read_text())
        self.assertEqual(len(loaded["projects"]), 1)
        self.assertEqual(loaded["projects"][0]["name"], "test")
        self.assertEqual(len(loaded["codex"]), 1)

    def test_frontmatter_date_as_date_object(self):
        """YAML may parse dates as date objects; ensure we convert to str."""
        md = "---\ntitle: Test\ncreated: 2026-03-09\nupdated: 2026-03-09\n---\n\nContent"
        (self.codex_dir / "test.md").write_text(md)
        entries = load_codex()
        self.assertEqual(entries[0].created, "2026-03-09")
        self.assertIsInstance(entries[0].created, str)


class TestCodexCategories(unittest.TestCase):
    def test_codex_kinds_exist_and_differ_from_default(self):
        """Codex has its own kind set, distinct from DEFAULT_DOMAINS."""
        from nexus import CODEX_KINDS, DEFAULT_DOMAINS
        self.assertIsInstance(CODEX_KINDS, list)
        self.assertTrue(len(CODEX_KINDS) > 0)
        self.assertNotEqual(set(CODEX_KINDS), set(DEFAULT_DOMAINS))

    def test_codex_default_kind_is_in_codex_kinds(self):
        """CodexEntry default kind must exist in CODEX_KINDS."""
        from nexus import CODEX_KINDS
        entry = CodexEntry()
        self.assertIn(entry.kind, CODEX_KINDS)


if __name__ == "__main__":
    unittest.main()
