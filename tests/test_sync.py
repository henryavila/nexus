import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nexus.sync import pull_rebase


class PullRebaseTests(unittest.TestCase):
    def test_pull_rebase_success(self):
        def fake_run(cmd, **kw):
            if "remote" in cmd:
                return subprocess.CompletedProcess(cmd, 0, stdout="origin\n", stderr="")
            if "pull" in cmd:
                return subprocess.CompletedProcess(cmd, 0, stdout="ok\n", stderr="")
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        with patch("nexus.sync.subprocess.run", side_effect=fake_run):
            ok, msg = pull_rebase("/fake/repo")
        self.assertTrue(ok)

    def test_pull_rebase_no_remote(self):
        def fake_run(cmd, **kw):
            return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="")

        with patch("nexus.sync.subprocess.run", side_effect=fake_run):
            ok, msg = pull_rebase("/fake/repo")
        self.assertTrue(ok)  # no remote = skip, not error
        self.assertIn("sem remote", msg)

    def test_pull_rebase_conflict(self):
        def fake_run(cmd, **kw):
            if "remote" in cmd:
                return subprocess.CompletedProcess(cmd, 0, stdout="origin\n", stderr="")
            if "pull" in cmd:
                return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="CONFLICT")
            if "rebase" in cmd and "--abort" in cmd:
                return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        with patch("nexus.sync.subprocess.run", side_effect=fake_run):
            ok, msg = pull_rebase("/fake/repo")
        self.assertFalse(ok)
        self.assertIn("CONFLICT", msg)


class TestAutoSyncNewFiles(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmpdir.name)
        subprocess.run(["git", "init"], cwd=self.repo, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=self.repo, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=self.repo, capture_output=True)
        (self.repo / "data").mkdir()
        (self.repo / "data" / "projects.yml").write_text("projects: []\n")
        (self.repo / "data" / "ideas.yml").write_text("ideas: []\n")
        subprocess.run(["git", "add", "."], cwd=self.repo, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=self.repo, capture_output=True)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_stages_apps_yml(self):
        (self.repo / "data" / "apps.yml").write_text("apps: []\n")
        from nexus.sync import auto_sync_registry
        result = auto_sync_registry(str(self.repo), "test")
        self.assertTrue(result)
        # Verify the file was committed
        log = subprocess.run(
            ["git", "log", "--oneline", "-1"],
            cwd=self.repo, capture_output=True, text=True,
        )
        self.assertIn("nexus-auto", log.stdout)
        # Verify apps.yml is tracked
        show = subprocess.run(
            ["git", "show", "HEAD:data/apps.yml"],
            cwd=self.repo, capture_output=True, text=True,
        )
        self.assertEqual(show.returncode, 0)

    def test_stages_environments_yml(self):
        (self.repo / "data" / "environments.yml").write_text("environments: []\n")
        from nexus.sync import auto_sync_registry
        result = auto_sync_registry(str(self.repo), "test")
        self.assertTrue(result)
        show = subprocess.run(
            ["git", "show", "HEAD:data/environments.yml"],
            cwd=self.repo, capture_output=True, text=True,
        )
        self.assertEqual(show.returncode, 0)

    def test_stages_skills_md_only(self):
        skills_dir = self.repo / "data" / "skills"
        skills_dir.mkdir()
        (skills_dir / "test.md").write_text("---\ntitle: test\n---\n")
        (skills_dir / "temp.swp").write_text("junk")
        from nexus.sync import auto_sync_registry
        result = auto_sync_registry(str(self.repo), "test")
        self.assertTrue(result)
        # .md file should be committed
        show_md = subprocess.run(
            ["git", "show", "HEAD:data/skills/test.md"],
            cwd=self.repo, capture_output=True, text=True,
        )
        self.assertEqual(show_md.returncode, 0)
        # .swp file should NOT be committed
        show_swp = subprocess.run(
            ["git", "show", "HEAD:data/skills/temp.swp"],
            cwd=self.repo, capture_output=True, text=True,
        )
        self.assertNotEqual(show_swp.returncode, 0)

    def test_no_error_when_apps_yml_missing(self):
        """auto_sync_registry should succeed even if apps.yml doesn't exist."""
        from nexus.sync import auto_sync_registry
        # Modify projects.yml to trigger a commit
        (self.repo / "data" / "projects.yml").write_text("projects: [modified]\n")
        result = auto_sync_registry(str(self.repo), "test")
        self.assertTrue(result)

    def test_no_error_when_environments_yml_missing(self):
        """auto_sync_registry should succeed even if environments.yml doesn't exist."""
        from nexus.sync import auto_sync_registry
        (self.repo / "data" / "projects.yml").write_text("projects: [modified]\n")
        result = auto_sync_registry(str(self.repo), "test")
        self.assertTrue(result)


class TestCommitAndPush(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmpdir.name)
        subprocess.run(["git", "init"], cwd=self.repo, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"],
                       cwd=self.repo, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"],
                       cwd=self.repo, capture_output=True)
        (self.repo / "data").mkdir()
        (self.repo / "data" / "projects.yml").write_text("projects: []\n")
        (self.repo / "data" / "ideas.yml").write_text("ideas: []\n")
        subprocess.run(["git", "add", "."], cwd=self.repo, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"],
                       cwd=self.repo, capture_output=True)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_commits_only_specified_files(self):
        """_commit_and_push stages only the given files."""
        from nexus.sync import _commit_and_push
        (self.repo / "data" / "projects.yml").write_text("- name: x\n")
        (self.repo / "data" / "ideas.yml").write_text("- title: y\n")
        result = _commit_and_push(
            str(self.repo), ["data/projects.yml"], "test"
        )
        self.assertTrue(result)
        show = subprocess.run(
            ["git", "show", "--stat", "HEAD"],
            cwd=self.repo, capture_output=True, text=True,
        )
        self.assertIn("projects.yml", show.stdout)
        self.assertNotIn("ideas.yml", show.stdout)
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=self.repo, capture_output=True, text=True,
        )
        self.assertIn("ideas.yml", status.stdout)

    def test_no_changes_returns_true(self):
        """If specified files have no changes, return True without commit."""
        from nexus.sync import _commit_and_push
        result = _commit_and_push(
            str(self.repo), ["data/projects.yml"], "test"
        )
        self.assertTrue(result)
        log = subprocess.run(
            ["git", "log", "--oneline"],
            cwd=self.repo, capture_output=True, text=True,
        )
        self.assertEqual(len(log.stdout.strip().split("\n")), 1)

    def test_commit_message_format(self):
        """Commit message follows [nexus-auto] pattern."""
        from nexus.sync import _commit_and_push
        (self.repo / "data" / "projects.yml").write_text("- name: x\n")
        _commit_and_push(str(self.repo), ["data/projects.yml"], "edit")
        msg = subprocess.run(
            ["git", "log", "-1", "--format=%s"],
            cwd=self.repo, capture_output=True, text=True,
        )
        self.assertEqual(msg.stdout.strip(), "[nexus-auto] edit sync")

    def test_glob_pattern_expands_and_filters(self):
        """Glob patterns like 'data/skills/*.md' expand to only .md files."""
        from nexus.sync import _commit_and_push
        skills = self.repo / "data" / "skills"
        skills.mkdir()
        (skills / "test.md").write_text("# skill\n")
        (skills / "temp.swp").write_text("junk")
        subprocess.run(["git", "add", "."], cwd=self.repo, capture_output=True)
        subprocess.run(["git", "commit", "-m", "add skills dir"],
                       cwd=self.repo, capture_output=True)
        (skills / "test.md").write_text("# updated\n")
        (skills / "temp.swp").write_text("more junk")
        result = _commit_and_push(
            str(self.repo), ["data/skills/*.md"], "skill-edit"
        )
        self.assertTrue(result)
        show = subprocess.run(
            ["git", "show", "--stat", "HEAD"],
            cwd=self.repo, capture_output=True, text=True,
        )
        self.assertIn("test.md", show.stdout)
        self.assertNotIn("temp.swp", show.stdout)

    def test_glob_nonexistent_dir_returns_true(self):
        """Glob on non-existent dir returns True (no files = no changes)."""
        from nexus.sync import _commit_and_push
        result = _commit_and_push(
            str(self.repo), ["data/skills/*.md"], "skill-edit"
        )
        self.assertTrue(result)


class TestQuickSync(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmpdir.name)
        subprocess.run(["git", "init"], cwd=self.repo, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"],
                       cwd=self.repo, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"],
                       cwd=self.repo, capture_output=True)
        (self.repo / "data").mkdir()
        (self.repo / "data" / "projects.yml").write_text("projects: []\n")
        (self.repo / "data" / "ideas.yml").write_text("ideas: []\n")
        (self.repo / "data" / "codex").mkdir()
        subprocess.run(["git", "add", "."], cwd=self.repo, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"],
                       cwd=self.repo, capture_output=True)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_quick_sync_single_file(self):
        """quick_sync commits only the specified file."""
        from nexus.sync import quick_sync
        (self.repo / "data" / "ideas.yml").write_text("- title: new\n")
        result = quick_sync(str(self.repo), ["data/ideas.yml"], "idea-add")
        self.assertTrue(result)
        msg = subprocess.run(
            ["git", "log", "-1", "--format=%s"],
            cwd=self.repo, capture_output=True, text=True,
        )
        self.assertIn("idea-add", msg.stdout)

    def test_quick_sync_directory(self):
        """quick_sync handles directory paths (codex/)."""
        from nexus.sync import quick_sync
        (self.repo / "data" / "codex" / "test.md").write_text("# test\n")
        result = quick_sync(str(self.repo), ["data/codex/"], "codex-add")
        self.assertTrue(result)
        show = subprocess.run(
            ["git", "show", "HEAD:data/codex/test.md"],
            cwd=self.repo, capture_output=True, text=True,
        )
        self.assertEqual(show.returncode, 0)

    def test_quick_sync_does_not_touch_other_files(self):
        """quick_sync leaves unrelated dirty files alone."""
        from nexus.sync import quick_sync
        (self.repo / "data" / "ideas.yml").write_text("- title: new\n")
        (self.repo / "data" / "projects.yml").write_text("- name: new\n")
        quick_sync(str(self.repo), ["data/ideas.yml"], "idea-add")
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=self.repo, capture_output=True, text=True,
        )
        self.assertIn("projects.yml", status.stdout)


if __name__ == "__main__":
    unittest.main()
