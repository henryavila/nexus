import argparse
import subprocess
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from nexus.sync import auto_sync_registry


class TestAutoSyncRegistry(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmpdir.name)
        # Init a git repo with a remote
        subprocess.run(["git", "init"], cwd=self.repo, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=self.repo, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=self.repo, capture_output=True)
        # Create and commit initial files
        (self.repo / "data").mkdir()
        (self.repo / "data" / "projects.yml").write_text("[]")
        (self.repo / "data" / "ideas.yml").write_text("[]")
        subprocess.run(["git", "add", "."], cwd=self.repo, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=self.repo, capture_output=True)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_no_changes_no_commit(self):
        """No dirty data files → no commit created."""
        result = auto_sync_registry(str(self.repo), "add")
        self.assertTrue(result)
        log = subprocess.run(["git", "log", "--oneline"], cwd=self.repo, capture_output=True, text=True)
        self.assertEqual(len(log.stdout.strip().split("\n")), 1)  # only init

    def test_dirty_projects_yml_commits(self):
        """Modified projects.yml → auto-commit created."""
        (self.repo / "data" / "projects.yml").write_text("- name: test")
        result = auto_sync_registry(str(self.repo), "add")
        self.assertTrue(result)
        log = subprocess.run(["git", "log", "--oneline"], cwd=self.repo, capture_output=True, text=True)
        self.assertEqual(len(log.stdout.strip().split("\n")), 2)

    def test_dirty_ideas_yml_commits(self):
        """Modified ideas.yml → auto-commit created."""
        (self.repo / "data" / "ideas.yml").write_text("- title: test idea")
        result = auto_sync_registry(str(self.repo), "idea add")
        self.assertTrue(result)
        log = subprocess.run(["git", "log", "--oneline"], cwd=self.repo, capture_output=True, text=True)
        self.assertEqual(len(log.stdout.strip().split("\n")), 2)
        # Verify commit message mentions the command
        log_msg = subprocess.run(["git", "log", "-1", "--format=%s"], cwd=self.repo, capture_output=True, text=True)
        self.assertIn("idea add", log_msg.stdout)

    def test_commit_message_format(self):
        """Commit message follows pattern: [nexus-auto] <command> sync"""
        (self.repo / "data" / "projects.yml").write_text("- name: x")
        auto_sync_registry(str(self.repo), "edit")
        msg = subprocess.run(["git", "log", "-1", "--format=%s"], cwd=self.repo, capture_output=True, text=True)
        self.assertEqual(msg.stdout.strip(), "[nexus-auto] edit sync")

    def test_only_stages_data_files(self):
        """Other modified files are NOT staged."""
        (self.repo / "data" / "projects.yml").write_text("- name: x")
        (self.repo / "other.txt").write_text("should not be committed")
        auto_sync_registry(str(self.repo), "add")
        show = subprocess.run(["git", "show", "--stat", "HEAD"], cwd=self.repo, capture_output=True, text=True)
        self.assertNotIn("other.txt", show.stdout)

    def test_no_remote_skips_push(self):
        """No remote → commit only, no push, still returns True."""
        (self.repo / "data" / "projects.yml").write_text("- name: x")
        result = auto_sync_registry(str(self.repo), "add")
        self.assertTrue(result)

    def test_push_failure_returns_false(self):
        """Push failure → returns False but commit is preserved."""
        # Add a fake remote that will fail
        subprocess.run(["git", "remote", "add", "origin", "https://invalid.invalid/repo.git"],
                       cwd=self.repo, capture_output=True)
        (self.repo / "data" / "projects.yml").write_text("- name: x")
        result = auto_sync_registry(str(self.repo), "add")
        self.assertFalse(result)
        # Commit should still exist
        log = subprocess.run(["git", "log", "--oneline"], cwd=self.repo, capture_output=True, text=True)
        self.assertEqual(len(log.stdout.strip().split("\n")), 2)

    def test_silent_on_failure(self):
        """Git errors don't raise exceptions."""
        result = auto_sync_registry("/nonexistent/path", "add")
        self.assertFalse(result)


class TestAutoSyncPullBeforeCommit(unittest.TestCase):
    """auto_sync_registry should pull before committing and use merge
    as fallback when rebase fails, to handle multi-PC scenarios."""

    def _make_repo_pair(self):
        """Create a bare 'remote' + two clones simulating two PCs."""
        import shutil
        base = tempfile.mkdtemp()
        bare = Path(base) / "remote.git"
        subprocess.run(["git", "init", "--bare", str(bare)], capture_output=True)

        pc_a = Path(base) / "pc_a"
        subprocess.run(["git", "clone", str(bare), str(pc_a)], capture_output=True)
        subprocess.run(["git", "config", "user.email", "a@test.com"], cwd=pc_a, capture_output=True)
        subprocess.run(["git", "config", "user.name", "A"], cwd=pc_a, capture_output=True)
        (pc_a / "data").mkdir()
        (pc_a / "data" / "projects.yml").write_text("projects: []\n")
        (pc_a / "data" / "ideas.yml").write_text("ideas: []\n")
        (pc_a / "data" / "environments.yml").write_text(
            "environments:\n"
            "- hostname: PC-A\n"
            "  last_seen: '2026-03-17'\n"
            "- hostname: PC-B\n"
            "  last_seen: '2026-03-17'\n"
        )
        subprocess.run(["git", "add", "."], cwd=pc_a, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=pc_a, capture_output=True)
        subprocess.run(["git", "push"], cwd=pc_a, capture_output=True)

        pc_b = Path(base) / "pc_b"
        subprocess.run(["git", "clone", str(bare), str(pc_b)], capture_output=True)
        subprocess.run(["git", "config", "user.email", "b@test.com"], cwd=pc_b, capture_output=True)
        subprocess.run(["git", "config", "user.name", "B"], cwd=pc_b, capture_output=True)

        self._base = base
        return pc_a, pc_b

    def tearDown(self):
        import shutil
        if hasattr(self, "_base"):
            shutil.rmtree(self._base, ignore_errors=True)

    def test_true_conflict_warns_and_returns_false(self):
        """Same-line conflict (unrebaseable AND unmergeable) should return
        False and print a warning to stderr."""
        pc_a, pc_b = self._make_repo_pair()

        # PC-A rewrites projects.yml and pushes
        (pc_a / "data" / "projects.yml").write_text("projects:\n- name: version-a\n")
        auto_sync_registry(str(pc_a), "edit")

        # PC-B rewrites the SAME line with different content
        (pc_b / "data" / "projects.yml").write_text("projects:\n- name: version-b\n")

        import io
        captured = io.StringIO()
        with patch("sys.stderr", captured):
            result = auto_sync_registry(str(pc_b), "edit")

        self.assertFalse(result)
        self.assertIn("sync", captured.getvalue().lower())

    def test_merge_fallback_handles_adjacent_changes(self):
        """When two PCs add entries to different YAML lists in the same file,
        the merge fallback should resolve the conflict if rebase can't."""
        pc_a, pc_b = self._make_repo_pair()

        # Start with a bigger file so changes are clearly separated
        base_env = (
            "environments:\n"
            "- hostname: PC-A\n"
            "  name: PC-A\n"
            "  location: Home\n"
            "  last_seen: '2026-03-17'\n"
            "\n"
            "- hostname: PC-B\n"
            "  name: PC-B\n"
            "  location: Work\n"
            "  last_seen: '2026-03-17'\n"
        )
        # Reset both PCs with the bigger file
        (pc_a / "data" / "environments.yml").write_text(base_env)
        subprocess.run(["git", "add", "data/environments.yml"], cwd=pc_a, capture_output=True)
        subprocess.run(["git", "commit", "-m", "bigger env"], cwd=pc_a, capture_output=True)
        subprocess.run(["git", "push"], cwd=pc_a, capture_output=True)
        subprocess.run(["git", "pull"], cwd=pc_b, capture_output=True)

        # PC-A updates its entry
        (pc_a / "data" / "environments.yml").write_text(
            base_env.replace("PC-A\n  last_seen: '2026-03-17'",
                             "PC-A\n  last_seen: '2026-03-18'")
        )
        auto_sync_registry(str(pc_a), "scan")

        # PC-B updates its entry (different block, different lines)
        (pc_b / "data" / "environments.yml").write_text(
            base_env.replace("PC-B\n  last_seen: '2026-03-17'",
                             "PC-B\n  last_seen: '2026-03-18'")
        )
        result = auto_sync_registry(str(pc_b), "scan")
        self.assertTrue(result, "Disjoint changes should sync successfully")

    def test_sync_prints_warning_on_failure(self):
        """When sync fails, a warning should be printed to stderr."""
        pc_a, pc_b = self._make_repo_pair()

        # Create conflict that even merge can't resolve
        # (we simulate total push failure with invalid remote)
        subprocess.run(["git", "remote", "set-url", "origin", "https://invalid.invalid/repo.git"],
                       cwd=pc_b, capture_output=True)
        (pc_b / "data" / "projects.yml").write_text("projects:\n- name: x\n")

        import io, sys
        captured = io.StringIO()
        with patch("sys.stderr", captured):
            result = auto_sync_registry(str(pc_b), "edit")

        self.assertFalse(result)
        output = captured.getvalue()
        self.assertIn("sync", output.lower(),
                      "Should print warning about sync failure to stderr")


class TestAutoUpdateWarning(unittest.TestCase):
    """_auto_update() should warn the user when pull fails, not fail silently."""

    @patch.dict("os.environ", {}, clear=False)
    @patch("nexus._legacy_main.subprocess.run")
    def test_auto_update_warns_on_pull_failure(self, mock_run):
        """When git pull --rebase fails, _auto_update should print a warning."""
        import os
        os.environ.pop("_NEXUS_UPDATED", None)

        def fake_run(cmd, **kw):
            if "rev-parse" in cmd:
                return subprocess.CompletedProcess(cmd, 0, stdout="abc123\n", stderr="")
            if "remote" in cmd:
                return subprocess.CompletedProcess(cmd, 0, stdout="origin\n", stderr="")
            if "pull" in cmd:
                return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="CONFLICT in environments.yml")
            if "rebase" in cmd and "--abort" in cmd:
                return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        mock_run.side_effect = fake_run

        import io
        captured = io.StringIO()
        import nexus._legacy_main as m
        with patch("sys.stderr", captured):
            m._auto_update()

        output = captured.getvalue()
        self.assertIn("sync", output.lower(),
                      "_auto_update should warn when pull fails")


class TestMainAutoSync(unittest.TestCase):
    @patch("nexus._legacy_main.quick_sync")
    @patch("nexus._legacy_main._auto_update")
    def test_mutating_command_triggers_sync(self, mock_update, mock_quick):
        """Commands in _MUTATING_COMMANDS trigger quick_sync."""
        mock_quick.return_value = True
        import nexus._legacy_main as m
        with patch.object(m, "build_parser") as mock_parser:
            ns = argparse.Namespace(command="add")
            ns.func = lambda a: 0
            mock_parser.return_value.parse_args.return_value = ns
            with self.assertRaises(SystemExit):
                m.main()
        mock_quick.assert_called_once()

    @patch("nexus._legacy_main.quick_sync")
    @patch("nexus._legacy_main.auto_sync_registry")
    @patch("nexus._legacy_main._auto_update")
    def test_readonly_command_skips_sync(self, mock_update, mock_full, mock_quick):
        """Commands NOT in _MUTATING_COMMANDS skip sync entirely."""
        import nexus._legacy_main as m
        with patch.object(m, "build_parser") as mock_parser:
            ns = argparse.Namespace(command="list")
            ns.func = lambda a: 0
            mock_parser.return_value.parse_args.return_value = ns
            with self.assertRaises(SystemExit):
                m.main()
        mock_quick.assert_not_called()
        mock_full.assert_not_called()

    @patch("nexus._legacy_main.quick_sync")
    @patch("nexus._legacy_main.auto_sync_registry")
    @patch("nexus._legacy_main._auto_update")
    def test_failed_command_skips_sync(self, mock_update, mock_full, mock_quick):
        """Commands that return non-zero skip sync."""
        import nexus._legacy_main as m
        with patch.object(m, "build_parser") as mock_parser:
            ns = argparse.Namespace(command="add")
            ns.func = lambda a: 1  # failure
            mock_parser.return_value.parse_args.return_value = ns
            with self.assertRaises(SystemExit):
                m.main()
        mock_quick.assert_not_called()
        mock_full.assert_not_called()


class TestMainQuickSync(unittest.TestCase):
    """CLI mutating commands should use quick_sync with specific files."""

    @patch("nexus._legacy_main.quick_sync")
    @patch("nexus._legacy_main.auto_sync_registry")
    @patch("nexus._legacy_main._auto_update")
    def test_idea_command_uses_quick_sync(self, mock_update, mock_full, mock_quick):
        """'idea' command should call quick_sync with ideas.yml + projects.yml."""
        mock_quick.return_value = True
        import nexus._legacy_main as m
        with patch.object(m, "build_parser") as mock_parser:
            ns = argparse.Namespace(command="idea")
            ns.func = lambda a: 0
            mock_parser.return_value.parse_args.return_value = ns
            with self.assertRaises(SystemExit):
                m.main()
        mock_quick.assert_called_once()
        files_arg = mock_quick.call_args[0][1]
        self.assertEqual(files_arg, ["data/ideas.yml", "data/projects.yml", "data/apps.yml"])
        mock_full.assert_not_called()

    @patch("nexus._legacy_main.quick_sync")
    @patch("nexus._legacy_main.auto_sync_registry")
    @patch("nexus._legacy_main._auto_update")
    def test_scan_command_uses_full_sync(self, mock_update, mock_full, mock_quick):
        """'scan' command should use auto_sync_registry (full sync)."""
        mock_full.return_value = True
        import nexus._legacy_main as m
        with patch.object(m, "build_parser") as mock_parser:
            ns = argparse.Namespace(command="scan")
            ns.func = lambda a: 0
            mock_parser.return_value.parse_args.return_value = ns
            with self.assertRaises(SystemExit):
                m.main()
        mock_full.assert_called_once()
        mock_quick.assert_not_called()

    @patch("nexus._legacy_main.quick_sync")
    @patch("nexus._legacy_main.auto_sync_registry")
    @patch("nexus._legacy_main._auto_update")
    def test_codex_command_uses_quick_sync_with_dir(self, mock_update, mock_full, mock_quick):
        """'codex' command should call quick_sync with data/codex/."""
        mock_quick.return_value = True
        import nexus._legacy_main as m
        with patch.object(m, "build_parser") as mock_parser:
            ns = argparse.Namespace(command="codex")
            ns.func = lambda a: 0
            mock_parser.return_value.parse_args.return_value = ns
            with self.assertRaises(SystemExit):
                m.main()
        mock_quick.assert_called_once()
        files_arg = mock_quick.call_args[0][1]
        self.assertEqual(files_arg, ["data/codex/"])
