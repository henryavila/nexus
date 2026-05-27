"""Tests for AppEntry CRUD operations."""

import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from nexus.apps import AppEntry, load_apps, save_apps, add_app, resolve_app, remove_app


class TestAppEntry(unittest.TestCase):
    def test_defaults(self):
        a = AppEntry(name="Test")
        self.assertEqual(a.name, "Test")
        self.assertEqual(a.slug, "")
        self.assertIsNone(a.github)
        self.assertIsNone(a.url)

    def test_all_fields(self):
        a = AppEntry(
            name="ARCH", slug="arch", description="desc",
            icon="\U0001F3DB", domain="trabalho",
            github="https://github.com/x", url="https://arch.com",
            added="2026-03-10",
        )
        self.assertEqual(a.domain, "trabalho")


class TestAppCRUD(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.apps_yml = Path(self.tmpdir.name) / "apps.yml"
        self.projects_yml = Path(self.tmpdir.name) / "projects.yml"
        self.patches = [
            patch("nexus.apps.APPS_YML", self.apps_yml),
            patch("nexus.registry.PROJECTS_YML", self.projects_yml),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.tmpdir.cleanup()

    def test_load_empty(self):
        self.assertEqual(load_apps(), [])

    def test_roundtrip(self):
        app = AppEntry(name="Nexus", slug="nexus", domain="tech")
        save_apps([app])
        loaded = load_apps()
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0].name, "Nexus")
        self.assertEqual(loaded[0].slug, "nexus")

    def test_add_app_generates_slug(self):
        app = AppEntry(name="My App")
        result = add_app(app)
        self.assertNotEqual(result.slug, "")
        self.assertEqual(result.slug, "my-app")

    def test_add_app_sets_added_date(self):
        app = AppEntry(name="Test")
        result = add_app(app)
        self.assertNotEqual(result.added, "")

    def test_add_app_preserves_existing_slug(self):
        app = AppEntry(name="My App", slug="custom-slug")
        result = add_app(app)
        self.assertEqual(result.slug, "custom-slug")

    def test_add_app_persists(self):
        add_app(AppEntry(name="Alpha"))
        apps = load_apps()
        self.assertEqual(len(apps), 1)
        self.assertEqual(apps[0].name, "Alpha")

    def test_resolve_by_slug(self):
        save_apps([AppEntry(name="Nexus", slug="nexus")])
        entry, _ = resolve_app("nexus")
        self.assertIsNotNone(entry)

    def test_resolve_by_name(self):
        save_apps([AppEntry(name="Nexus", slug="nexus")])
        entry, _ = resolve_app("Nexus")
        self.assertIsNotNone(entry)

    def test_resolve_partial(self):
        save_apps([AppEntry(name="Nexus App", slug="nexus")])
        entry, _ = resolve_app("nex")
        self.assertIsNotNone(entry)

    def test_resolve_no_match(self):
        save_apps([AppEntry(name="Nexus", slug="nexus")])
        entry, candidates = resolve_app("zzz")
        self.assertIsNone(entry)
        self.assertEqual(candidates, [])

    def test_resolve_multiple_partial(self):
        save_apps([
            AppEntry(name="Nexus One", slug="nexus-one"),
            AppEntry(name="Nexus Two", slug="nexus-two"),
        ])
        entry, candidates = resolve_app("nexus")
        self.assertIsNone(entry)
        self.assertEqual(len(candidates), 2)

    def test_resolve_empty(self):
        entry, candidates = resolve_app("anything")
        self.assertIsNone(entry)
        self.assertEqual(candidates, [])

    def test_note_roundtrip(self):
        save_apps([AppEntry(name="X", slug="x", note="test note")])
        loaded = load_apps()
        self.assertEqual(loaded[0].note, "test note")

    def test_note_omitted_when_none(self):
        save_apps([AppEntry(name="X", slug="x")])
        text = self.apps_yml.read_text()
        self.assertNotIn("note", text)

    def test_save_omits_none_fields(self):
        save_apps([AppEntry(name="X", slug="x")])
        text = self.apps_yml.read_text()
        self.assertNotIn("github", text)
        self.assertNotIn("url", text)
        self.assertNotIn("icon", text)

    def test_remove_app_success(self):
        save_apps([AppEntry(name="Nexus", slug="nexus")])
        result = remove_app("nexus")
        self.assertTrue(result)
        self.assertEqual(load_apps(), [])

    def test_remove_app_not_found(self):
        save_apps([AppEntry(name="Nexus", slug="nexus")])
        result = remove_app("nonexistent")
        self.assertFalse(result)
        self.assertEqual(len(load_apps()), 1)

    def test_remove_app_empty_list(self):
        result = remove_app("anything")
        self.assertFalse(result)


class TestSlugify(unittest.TestCase):
    def test_slugify_basic(self):
        from nexus.apps import _slugify
        self.assertEqual(_slugify("My App"), "my-app")

    def test_slugify_special_chars(self):
        from nexus.apps import _slugify
        self.assertEqual(_slugify("Hello, World!"), "hello-world")

    def test_slugify_multiple_spaces(self):
        from nexus.apps import _slugify
        self.assertEqual(_slugify("A  B"), "a-b")

    def test_slugify_underscores(self):
        from nexus.apps import _slugify
        self.assertEqual(_slugify("my_app"), "my-app")

    def test_slugify_leading_trailing(self):
        from nexus.apps import _slugify
        self.assertEqual(_slugify("  trimmed  "), "trimmed")


