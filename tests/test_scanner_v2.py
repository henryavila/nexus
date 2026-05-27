import unittest
import tempfile
import subprocess
from pathlib import Path
from datetime import datetime
from unittest.mock import patch

from nexus.scanner import scan_project


class TestScanGitProject(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)
        subprocess.run(["git", "init"], cwd=self.root, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=self.root, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=self.root, capture_output=True)
        (self.root / "file.txt").write_text("hello")
        subprocess.run(["git", "add", "."], cwd=self.root, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=self.root, capture_output=True)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_detects_git_class(self):
        result = scan_project(str(self.root))
        self.assertEqual(result["class"], "git")

    def test_has_git_fields(self):
        result = scan_project(str(self.root))
        git = result["git"]
        self.assertIn("branch", git)
        self.assertIn("dirty", git)
        self.assertIn("last_commit_date", git)
        self.assertIn("last_commit_message", git)

    def test_no_removed_fields(self):
        result = scan_project(str(self.root))
        self.assertNotIn("activity_history", result)
        self.assertNotIn("activity", result)
        self.assertNotIn("priority", result)
        self.assertNotIn("tasks", result)
        self.assertNotIn("type", result)

    def test_has_health_checks(self):
        result = scan_project(str(self.root))
        self.assertIn("health", result)
        self.assertIn("path_exists", result["health"])
        self.assertIn("claude_memory_portable", result["health"])

    def test_has_last_activity(self):
        result = scan_project(str(self.root))
        self.assertIsNotNone(result["last_activity"])


class TestScanFilesystemProject(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)
        (self.root / "notes.md").write_text("some notes")

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_detects_filesystem_class(self):
        result = scan_project(str(self.root))
        self.assertEqual(result["class"], "filesystem")

    def test_has_filesystem_fields(self):
        result = scan_project(str(self.root))
        fs = result["filesystem"]
        self.assertIn("last_modified_file", fs)
        self.assertIn("last_modified_date", fs)

    def test_no_git_field(self):
        result = scan_project(str(self.root))
        self.assertIsNone(result["git"])


class TestScanNonexistent(unittest.TestCase):
    def test_returns_none(self):
        result = scan_project("/nonexistent/path/xyz")
        self.assertIsNone(result)


class TestMergeScanWithRegistry(unittest.TestCase):
    def test_merge_uses_registry_fields(self):
        from nexus.registry import ProjectEntry
        from nexus.scanner import _merge_scan_with_registry

        entry = ProjectEntry(
            path="/tmp/test",
            name="Test Project",
            description="A test",
            icon="\U0001f9ea",
            domain="pessoal",
            url="https://example.com",
            added="2026-02-25",
        )
        scan_data = {
            "class": "git",
            "last_activity": "2026-02-25",
            "git": {"branch": "main", "dirty": False, "last_commit_date": "2026-02-25",
                     "last_commit_message": "init", "repo": "user/test"},
            "filesystem": None,
            "health": {"path_exists": True, "claude_memory_portable": None, "web_compliant": None},
            "last_scanned": "2026-02-25T12:00:00",
        }
        merged = _merge_scan_with_registry(entry, scan_data)
        self.assertEqual(merged["name"], "Test Project")
        self.assertEqual(merged["icon"], "\U0001f9ea")
        self.assertEqual(merged["repo"], "user/test")
        self.assertNotIn("repo", merged["git"])

    def test_archived_status_preserved(self):
        from nexus.registry import ProjectEntry
        from nexus.scanner import _merge_scan_with_registry

        entry = ProjectEntry(
            path="/tmp/test", name="Test", domain="pessoal", status="archived"
        )
        scan_data = {
            "class": "filesystem",
            "last_activity": "2026-02-25",
            "git": None,
            "filesystem": {"last_modified_file": "a.txt", "last_modified_date": "2026-02-25"},
            "health": {"path_exists": True, "claude_memory_portable": None, "web_compliant": None},
            "last_scanned": "2026-02-25T12:00:00",
        }
        merged = _merge_scan_with_registry(entry, scan_data)
        self.assertEqual(merged["status"], "archived")


class TestScanOneNoRegression(unittest.TestCase):
    """Verify scan_one doesn't regress last_activity from stale scans."""

    def test_keeps_newer_existing_activity(self):
        import json
        from unittest.mock import patch
        from nexus import scanner
        from nexus.registry import ProjectEntry

        with tempfile.TemporaryDirectory() as tmpdir:
            proj_dir = Path(tmpdir) / "myproj"
            proj_dir.mkdir()
            (proj_dir / "file.txt").write_text("hello")

            entry = ProjectEntry(path=str(proj_dir), name="myproj", domain="pessoal")

            data_json = Path(tmpdir) / "data.json"
            lock_file = Path(tmpdir) / ".lock"

            # Pre-populate with a future date (simulating another machine's scan)
            existing = {
                "version": "2.0",
                "last_full_scan": None,
                "projects": [{
                    "name": "myproj",
                    "path": str(proj_dir),
                    "last_activity": "2099-01-01",
                }],
            }
            data_json.write_text(json.dumps(existing))

            with patch.object(scanner, "DATA_JSON", data_json), \
                 patch.object(scanner, "LOCK_FILE", lock_file), \
                 patch.object(scanner, "load_registry", return_value=[entry]):
                result = scanner.scan_one(str(proj_dir))

            self.assertIsNotNone(result)

            # The saved last_activity should be the existing one (2099), not regressed
            saved = json.loads(data_json.read_text())
            proj = [p for p in saved["projects"] if p["name"] == "myproj"][0]
            self.assertEqual(proj["last_activity"], "2099-01-01")


class TestReconcileWithRegistry(unittest.TestCase):
    """reconcile_with_registry removes orphan entries from data.json."""

    def test_removes_orphan_project(self):
        import json
        from unittest.mock import patch
        from nexus import scanner
        from nexus.registry import ProjectEntry

        with tempfile.TemporaryDirectory() as tmpdir:
            proj_dir = Path(tmpdir) / "active"
            proj_dir.mkdir()
            (proj_dir / "file.txt").write_text("hello")

            entry = ProjectEntry(path=str(proj_dir), name="active", domain="pessoal")

            data_json = Path(tmpdir) / "data.json"
            lock_file = Path(tmpdir) / ".lock"

            existing = {
                "version": "2.0",
                "last_full_scan": None,
                "projects": [
                    {"name": "active", "path": str(proj_dir)},
                    {"name": "orphan", "path": "/old/removed/path"},
                ],
            }
            data_json.write_text(json.dumps(existing))

            with patch.object(scanner, "DATA_JSON", data_json), \
                 patch.object(scanner, "LOCK_FILE", lock_file), \
                 patch.object(scanner, "load_registry", return_value=[entry]):
                result = scanner.reconcile_with_registry()

            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]["name"], "active")

    def test_keeps_all_when_synced(self):
        import json
        from unittest.mock import patch
        from nexus import scanner
        from nexus.registry import ProjectEntry

        with tempfile.TemporaryDirectory() as tmpdir:
            entry = ProjectEntry(path="/some/path", name="proj", domain="pessoal")

            data_json = Path(tmpdir) / "data.json"
            lock_file = Path(tmpdir) / ".lock"

            existing = {
                "version": "2.0",
                "last_full_scan": None,
                "projects": [
                    {"name": "proj", "path": "/some/path"},
                ],
            }
            data_json.write_text(json.dumps(existing))

            with patch.object(scanner, "DATA_JSON", data_json), \
                 patch.object(scanner, "LOCK_FILE", lock_file), \
                 patch.object(scanner, "load_registry", return_value=[entry]):
                result = scanner.reconcile_with_registry()

            self.assertEqual(len(result), 1)


class TestDataJsonV3(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.data_json = Path(self.tmpdir.name) / "data.json"
        self.projects_yml = Path(self.tmpdir.name) / "projects.yml"
        self.env_yml = Path(self.tmpdir.name) / "environments.yml"
        self.apps_yml = Path(self.tmpdir.name) / "apps.yml"
        self.patches = [
            patch("nexus.scanner.DATA_JSON", self.data_json),
            patch("nexus.registry.PROJECTS_YML", self.projects_yml),
            patch("nexus.environment.ENVIRONMENTS_YML", self.env_yml),
            patch("nexus.apps.APPS_YML", self.apps_yml),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.tmpdir.cleanup()

    def test_read_data_v3_skeleton(self):
        from nexus.scanner import _read_data
        data = _read_data()
        self.assertEqual(data["version"], "3.0")
        self.assertIn("environments", data)
        self.assertIn("apps", data)
        self.assertIn("projects", data)
        self.assertIn("ideas", data)
        self.assertIn("codex", data)

    def test_health_per_environment(self):
        import json
        existing = {
            "version": "3.0",
            "projects": [{
                "name": "test",
                "slug": "test",
                "health": {
                    "path_exists": {"OTHER-HOST": True},
                    "claude_memory_portable": {"OTHER-HOST": True},
                },
            }],
            "environments": [],
            "apps": [],
                        "ideas": [],
            "codex": [],
        }
        self.data_json.write_text(json.dumps(existing))
        from nexus.scanner import _read_data
        data = _read_data()
        proj = data["projects"][0]
        self.assertIn("OTHER-HOST", proj["health"]["path_exists"])

    def test_upgrade_v2_to_v3(self):
        import json
        existing = {
            "version": "2.1",
            "last_full_scan": "2026-03-01T12:00:00",
            "projects": [{"name": "old"}],
            "ideas": [{"title": "idea1"}],
        }
        self.data_json.write_text(json.dumps(existing))
        from nexus.scanner import _read_data
        data = _read_data()
        self.assertEqual(data["version"], "3.0")
        self.assertIn("environments", data)
        self.assertIn("apps", data)
        # Existing data preserved
        self.assertEqual(len(data["projects"]), 1)
        self.assertEqual(len(data["ideas"]), 1)

    def test_merge_health_per_env_new_entry(self):
        from nexus.scanner import _merge_health_per_env
        existing_item = {}
        new_scan = {
            "health": {
                "path_exists": True,
                "claude_memory_portable": None,
                "web_compliant": None,
            }
        }
        _merge_health_per_env(existing_item, new_scan, "MY-HOST")
        health = existing_item["health"]
        self.assertEqual(health["path_exists"], {"MY-HOST": True})
        self.assertEqual(health["claude_memory_portable"], {"MY-HOST": None})
        self.assertEqual(health["web_compliant"], {"MY-HOST": None})

    def test_merge_health_per_env_preserves_other_hosts(self):
        from nexus.scanner import _merge_health_per_env
        existing_item = {
            "health": {
                "path_exists": {"OTHER-HOST": True},
                "claude_memory_portable": {"OTHER-HOST": True},
                "web_compliant": {"OTHER-HOST": False},
            }
        }
        new_scan = {
            "health": {
                "path_exists": True,
                "claude_memory_portable": False,
                "web_compliant": None,
            }
        }
        _merge_health_per_env(existing_item, new_scan, "MY-HOST")
        health = existing_item["health"]
        self.assertEqual(health["path_exists"]["OTHER-HOST"], True)
        self.assertEqual(health["path_exists"]["MY-HOST"], True)
        self.assertEqual(health["claude_memory_portable"]["OTHER-HOST"], True)
        self.assertEqual(health["claude_memory_portable"]["MY-HOST"], False)

    def test_merge_health_per_env_flat_migration(self):
        """When existing health has flat bool (pre-v3), migrate to dict."""
        from nexus.scanner import _merge_health_per_env
        existing_item = {
            "health": {
                "path_exists": True,
                "claude_memory_portable": None,
                "web_compliant": None,
            }
        }
        new_scan = {
            "health": {
                "path_exists": True,
                "claude_memory_portable": False,
                "web_compliant": None,
            }
        }
        _merge_health_per_env(existing_item, new_scan, "MY-HOST")
        health = existing_item["health"]
        # Flat bools should be migrated to dict
        self.assertIsInstance(health["path_exists"], dict)
        self.assertEqual(health["path_exists"]["MY-HOST"], True)

    def test_get_health_value_per_env_dict(self):
        """get_health_value extracts current hostname's value from per-env dict."""
        from nexus.scanner import get_health_value
        health = {"path_exists": {"HOST-A": True, "HOST-B": False}}
        self.assertTrue(get_health_value(health, "path_exists", hostname="HOST-A"))
        self.assertFalse(get_health_value(health, "path_exists", hostname="HOST-B"))

    def test_get_health_value_flat_format(self):
        """get_health_value handles flat boolean format (backward compat)."""
        from nexus.scanner import get_health_value
        health = {"path_exists": True, "claude_memory_portable": False}
        self.assertTrue(get_health_value(health, "path_exists"))
        self.assertFalse(get_health_value(health, "claude_memory_portable"))

    def test_get_health_value_none(self):
        """get_health_value returns None for missing keys."""
        from nexus.scanner import get_health_value
        health = {"path_exists": {"HOST-A": True}}
        self.assertIsNone(get_health_value(health, "path_exists", hostname="UNKNOWN"))
        self.assertIsNone(get_health_value(health, "nonexistent"))

    def test_reconcile_with_registry_matches_by_slug(self):
        """reconcile_with_registry keeps entries that match by slug."""
        import json
        from nexus import scanner
        from nexus.registry import ProjectEntry

        with tempfile.TemporaryDirectory() as tmpdir:
            entry = ProjectEntry(name="proj", domain="pessoal", slug="proj")
            entry.path = None  # No path — slug-only match

            data_json = Path(tmpdir) / "data.json"
            lock_file = Path(tmpdir) / ".lock"
            existing = {
                "version": "3.0",
                "last_full_scan": None,
                "projects": [
                    {"name": "proj-renamed", "slug": "proj", "path": ""},
                ],
                "apps": [], "environments": [],                 "ideas": [], "codex": [],
            }
            data_json.write_text(json.dumps(existing))

            with patch.object(scanner, "DATA_JSON", data_json), \
                 patch.object(scanner, "LOCK_FILE", lock_file), \
                 patch.object(scanner, "load_registry", return_value=[entry]):
                result = scanner.reconcile_with_registry()

            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]["slug"], "proj")

    def test_scan_one_by_slug(self):
        """scan_one accepts a slug identifier."""
        import json
        from nexus import scanner
        from nexus.registry import ProjectEntry

        proj_dir = Path(self.tmpdir.name) / "myproj"
        proj_dir.mkdir()
        (proj_dir / "file.txt").write_text("hello")

        entry = ProjectEntry(
            path=str(proj_dir), name="myproj", slug="myproj",
            domain="pessoal"
        )
        lock_file = Path(self.tmpdir.name) / ".lock"

        with patch.object(scanner, "LOCK_FILE", lock_file), \
             patch("nexus.scanner.load_registry", return_value=[entry]), \
             patch("nexus.scanner.resolve_by_slug_or_path", return_value=entry):
            result = scanner.scan_one("myproj")

        self.assertIsNotNone(result)
        self.assertEqual(result["name"], "myproj")

    def test_scan_all_v3_output(self):
        """scan_all produces v3.0 data with per-env health."""
        import json
        import yaml
        from nexus import scanner
        from nexus.registry import ProjectEntry

        proj_dir = Path(self.tmpdir.name) / "proj"
        proj_dir.mkdir()
        (proj_dir / "file.txt").write_text("hello")

        entry = ProjectEntry(
            path=str(proj_dir), name="proj", slug="proj",
            domain="pessoal"
        )
        self.projects_yml.write_text(yaml.dump(
            {"projects": [{"name": "proj", "slug": "proj", "path": str(proj_dir),
                           "domain": "pessoal"}]},
            allow_unicode=True
        ))
        lock_file = Path(self.tmpdir.name) / ".lock"

        with patch.object(scanner, "LOCK_FILE", lock_file), \
             patch("nexus.scanner.load_registry", return_value=[entry]), \
             patch("nexus.scanner.get_current_hostname", return_value="TEST-HOST"):
            data = scanner.scan_all()

        self.assertEqual(data["version"], "3.0")
        self.assertIn("environments", data)
        self.assertIn("apps", data)
        # Health should be per-env dict
        proj = data["projects"][0]
        health = proj["health"]
        self.assertIsInstance(health["path_exists"], dict)
        self.assertIn("TEST-HOST", health["path_exists"])

    def test_scan_all_preserves_other_env_health(self):
        """scan_all merge strategy preserves health from other environments."""
        import json
        import yaml
        from nexus import scanner
        from nexus.registry import ProjectEntry

        proj_dir = Path(self.tmpdir.name) / "proj"
        proj_dir.mkdir()
        (proj_dir / "file.txt").write_text("hello")

        entry = ProjectEntry(
            path=str(proj_dir), name="proj", slug="proj",
            domain="pessoal"
        )
        self.projects_yml.write_text(yaml.dump(
            {"projects": [{"name": "proj", "slug": "proj", "path": str(proj_dir),
                           "domain": "pessoal"}]},
            allow_unicode=True
        ))

        # Pre-populate data.json with health from another host
        existing = {
            "version": "3.0",
            "last_full_scan": None,
            "current_environment": None,
            "projects": [{
                "name": "proj",
                "slug": "proj",
                "path": str(proj_dir),
                "health": {
                    "path_exists": {"REMOTE-HOST": True},
                    "claude_memory_portable": {"REMOTE-HOST": True},
                    "web_compliant": {"REMOTE-HOST": None},
                },
            }],
            "apps": [],
            "environments": [],
                        "ideas": [],
            "codex": [],
        }
        self.data_json.write_text(json.dumps(existing))
        lock_file = Path(self.tmpdir.name) / ".lock"

        with patch.object(scanner, "LOCK_FILE", lock_file), \
             patch("nexus.scanner.load_registry", return_value=[entry]), \
             patch("nexus.scanner.get_current_hostname", return_value="LOCAL-HOST"):
            data = scanner.scan_all()

        proj = data["projects"][0]
        health = proj["health"]
        # Both hosts' data should be present
        self.assertIn("REMOTE-HOST", health["path_exists"])
        self.assertIn("LOCAL-HOST", health["path_exists"])
        self.assertEqual(health["path_exists"]["REMOTE-HOST"], True)


class TestScanAllCancellation(unittest.TestCase):
    """scan_all should stop early when cancelled callback returns True."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.data_json = Path(self.tmpdir.name) / "data.json"
        self.projects_yml = Path(self.tmpdir.name) / "projects.yml"
        self.env_yml = Path(self.tmpdir.name) / "environments.yml"
        self.apps_yml = Path(self.tmpdir.name) / "apps.yml"
        self.patches = [
            patch("nexus.scanner.DATA_JSON", self.data_json),
            patch("nexus.registry.PROJECTS_YML", self.projects_yml),
            patch("nexus.environment.ENVIRONMENTS_YML", self.env_yml),
            patch("nexus.apps.APPS_YML", self.apps_yml),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.tmpdir.cleanup()

    def test_scan_all_stops_early_when_cancelled(self):
        """scan_all should scan zero projects when cancelled immediately."""
        from nexus import scanner
        from nexus.registry import ProjectEntry

        dirs = []
        for i in range(3):
            d = Path(self.tmpdir.name) / f"proj{i}"
            d.mkdir()
            (d / "file.txt").write_text("hello")
            dirs.append(d)

        entries = [
            ProjectEntry(path=str(d), name=f"proj{i}", slug=f"proj{i}", domain="pessoal")
            for i, d in enumerate(dirs)
        ]
        lock_file = Path(self.tmpdir.name) / ".lock"

        scanned_names = []
        def on_progress(i, total, name):
            scanned_names.append(name)

        with patch.object(scanner, "LOCK_FILE", lock_file), \
             patch("nexus.scanner.load_registry", return_value=entries), \
             patch("nexus.scanner.get_current_hostname", return_value="TEST-HOST"):
            data = scanner.scan_all(
                on_progress=on_progress,
                cancelled=lambda: True,  # Cancel immediately
            )

        # Should have scanned 0 projects (cancelled before starting)
        self.assertEqual(len(data["projects"]), 0)

    def test_scan_all_stops_after_n_projects_when_cancelled(self):
        """scan_all should stop scanning after cancelled returns True."""
        from nexus import scanner
        from nexus.registry import ProjectEntry

        dirs = []
        for i in range(5):
            d = Path(self.tmpdir.name) / f"proj{i}"
            d.mkdir()
            (d / "file.txt").write_text("hello")
            dirs.append(d)

        entries = [
            ProjectEntry(path=str(d), name=f"proj{i}", slug=f"proj{i}", domain="pessoal")
            for i, d in enumerate(dirs)
        ]
        lock_file = Path(self.tmpdir.name) / ".lock"

        call_count = 0
        def cancel_after_2():
            nonlocal call_count
            call_count += 1
            return call_count > 2  # Cancel after 2 projects

        with patch.object(scanner, "LOCK_FILE", lock_file), \
             patch("nexus.scanner.load_registry", return_value=entries), \
             patch("nexus.scanner.get_current_hostname", return_value="TEST-HOST"):
            data = scanner.scan_all(cancelled=cancel_after_2)

        # Should have scanned at most 2 projects
        self.assertLessEqual(len(data["projects"]), 2)

    def test_scan_all_cancelled_does_not_overwrite_data_json(self):
        """When cancelled mid-scan, scan_all must NOT overwrite data.json with partial data.

        This is the root cause of the bug where removing one project via TUI
        causes other projects to disappear: the background scan is cancelled,
        but still writes data.json with only the projects scanned so far.
        """
        import json
        from nexus import scanner

        from nexus.registry import ProjectEntry

        dirs = []
        for i in range(5):
            d = Path(self.tmpdir.name) / f"proj{i}"
            d.mkdir()
            (d / "file.txt").write_text("hello")
            dirs.append(d)

        entries = [
            ProjectEntry(path=str(d), name=f"proj{i}", slug=f"proj{i}", domain="pessoal")
            for i, d in enumerate(dirs)
        ]
        lock_file = Path(self.tmpdir.name) / ".lock"

        # Pre-populate data.json with all 5 projects
        data_json = Path(self.tmpdir.name) / "data.json"
        existing_data = {
            "version": "3.0",
            "last_full_scan": "2026-03-27T10:00:00",
            "current_environment": "TEST-HOST",
            "projects": [
                {"name": f"proj{i}", "slug": f"proj{i}", "path": str(dirs[i])}
                for i in range(5)
            ],
            "apps": [], "environments": [], "ideas": [], "codex": [],
        }
        data_json.write_text(json.dumps(existing_data), encoding="utf-8")

        call_count = 0
        def cancel_after_2():
            nonlocal call_count
            call_count += 1
            return call_count > 2  # Cancel after 2 projects

        with patch.object(scanner, "LOCK_FILE", lock_file), \
             patch.object(scanner, "DATA_JSON", data_json), \
             patch("nexus.scanner.load_registry", return_value=entries), \
             patch("nexus.scanner.get_current_hostname", return_value="TEST-HOST"):
            scanner.scan_all(cancelled=cancel_after_2)

        # data.json must still have all 5 projects (not overwritten with partial data)
        saved = json.loads(data_json.read_text(encoding="utf-8"))
        self.assertEqual(len(saved["projects"]), 5,
                         "scan_all overwrote data.json with partial data when cancelled!")

    def test_scan_all_without_cancelled_scans_all(self):
        """scan_all without cancelled parameter scans all projects (backward compat)."""
        from nexus import scanner
        from nexus.registry import ProjectEntry

        dirs = []
        for i in range(3):
            d = Path(self.tmpdir.name) / f"proj{i}"
            d.mkdir()
            (d / "file.txt").write_text("hello")
            dirs.append(d)

        entries = [
            ProjectEntry(path=str(d), name=f"proj{i}", slug=f"proj{i}", domain="pessoal")
            for i, d in enumerate(dirs)
        ]
        lock_file = Path(self.tmpdir.name) / ".lock"

        with patch.object(scanner, "LOCK_FILE", lock_file), \
             patch("nexus.scanner.load_registry", return_value=entries), \
             patch("nexus.scanner.get_current_hostname", return_value="TEST-HOST"):
            data = scanner.scan_all()

        self.assertEqual(len(data["projects"]), 3)


class TestScanEnvironmentIntegration(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.env_yml = Path(self.tmpdir.name) / "environments.yml"
        self.patches = [
            patch("nexus.environment.ENVIRONMENTS_YML", self.env_yml),
            patch("nexus.scanner.get_current_hostname", return_value="TEST-HOST"),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.tmpdir.cleanup()

    def test_scan_updates_last_seen(self):
        from nexus.environment import save_environments, EnvironmentEntry, load_environments
        save_environments([
            EnvironmentEntry(hostname="TEST-HOST", name="Test", location="test", last_seen="2026-01-01")
        ])
        from nexus.environment import update_last_seen
        update_last_seen("TEST-HOST")
        loaded = load_environments()
        self.assertNotEqual(loaded[0].last_seen, "2026-01-01")


if __name__ == "__main__":
    unittest.main()
