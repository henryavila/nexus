"""Tests for git operation timeouts in _auto_update and sync functions.

Root cause: subprocess.run calls for git pull/push had no timeout parameter,
causing the app to hang indefinitely when the network is unavailable
(SSH TCP connect takes ~75s on macOS with default ConnectTimeout=none).
"""

import os
import subprocess
import unittest
from unittest.mock import patch, call, MagicMock


def _make_completed(cmd, returncode=0, stdout="", stderr=""):
    return subprocess.CompletedProcess(cmd, returncode, stdout=stdout, stderr=stderr)


class TestAutoUpdateTimeout(unittest.TestCase):
    """_auto_update must not hang when git pull is slow/unreachable."""

    def _import_auto_update(self):
        from nexus._legacy_main import _auto_update
        return _auto_update

    def test_auto_update_handles_pull_timeout(self):
        """Regression: git pull timeout must not block startup."""
        _auto_update = self._import_auto_update()

        calls = []

        def fake_run(cmd, **kw):
            calls.append(cmd)
            if "rev-parse" in cmd:
                return _make_completed(cmd, stdout="abc123\n")
            if cmd == ["git", "remote"]:
                return _make_completed(cmd, stdout="origin\n")
            if "pull" in cmd:
                raise subprocess.TimeoutExpired(cmd, kw.get("timeout", 10))
            if "rebase" in cmd and "--abort" in cmd:
                return _make_completed(cmd)
            return _make_completed(cmd)

        with patch.dict(os.environ, {"_NEXUS_UPDATED": ""}, clear=False), \
             patch("nexus._legacy_main.subprocess.run", side_effect=fake_run), \
             patch.dict(os.environ, {k: v for k, v in os.environ.items() if k != "_NEXUS_UPDATED"}):
            os.environ.pop("_NEXUS_UPDATED", None)
            _auto_update()

        pull_cmds = [c for c in calls if "pull" in c]
        self.assertTrue(len(pull_cmds) >= 1, "git pull should have been attempted")
        abort_cmds = [c for c in calls if "--abort" in c]
        self.assertTrue(len(abort_cmds) >= 1,
                        "rebase --abort should be called after timeout")

    def test_auto_update_skips_when_env_set(self):
        """Boundary: _NEXUS_UPDATED set => immediate return."""
        _auto_update = self._import_auto_update()

        with patch.dict(os.environ, {"_NEXUS_UPDATED": "1"}), \
             patch("nexus._legacy_main.subprocess.run") as mock_run:
            _auto_update()

        mock_run.assert_not_called()

    def test_auto_update_skips_without_remote(self):
        """Boundary: no git remote => skip pull entirely."""
        _auto_update = self._import_auto_update()

        def fake_run(cmd, **kw):
            if "rev-parse" in cmd:
                return _make_completed(cmd, stdout="abc123\n")
            if cmd == ["git", "remote"]:
                return _make_completed(cmd, stdout="")
            return _make_completed(cmd)

        with patch.dict(os.environ, {}, clear=False), \
             patch("nexus._legacy_main.subprocess.run", side_effect=fake_run):
            os.environ.pop("_NEXUS_UPDATED", None)
            _auto_update()

    def test_auto_update_timeout_no_pending_rebase(self):
        """Edge: after timeout, rebase --abort is called to clean up."""
        _auto_update = self._import_auto_update()

        rebase_abort_called = []

        def fake_run(cmd, **kw):
            if "rev-parse" in cmd:
                return _make_completed(cmd, stdout="abc123\n")
            if cmd == ["git", "remote"]:
                return _make_completed(cmd, stdout="origin\n")
            if "pull" in cmd:
                raise subprocess.TimeoutExpired(cmd, kw.get("timeout", 10))
            if "rebase" in cmd and "--abort" in cmd:
                rebase_abort_called.append(True)
                return _make_completed(cmd)
            return _make_completed(cmd)

        with patch.dict(os.environ, {}, clear=False), \
             patch("nexus._legacy_main.subprocess.run", side_effect=fake_run):
            os.environ.pop("_NEXUS_UPDATED", None)
            _auto_update()

        self.assertTrue(rebase_abort_called,
                        "rebase --abort must be called to prevent dirty state")

    def test_auto_update_normal_flow_preserved(self):
        """Edge: when pull succeeds and updates code, os.execv is called."""
        _auto_update = self._import_auto_update()

        call_count = {"rev-parse": 0}

        def fake_run(cmd, **kw):
            if "rev-parse" in cmd:
                call_count["rev-parse"] += 1
                if call_count["rev-parse"] == 1:
                    return _make_completed(cmd, stdout="old_hash\n")
                return _make_completed(cmd, stdout="new_hash\n")
            if cmd == ["git", "remote"]:
                return _make_completed(cmd, stdout="origin\n")
            if "pull" in cmd:
                return _make_completed(cmd, stdout="Updating...\n")
            return _make_completed(cmd)

        with patch.dict(os.environ, {}, clear=False), \
             patch("nexus._legacy_main.subprocess.run", side_effect=fake_run), \
             patch("nexus._legacy_main.os.execv") as mock_execv:
            os.environ.pop("_NEXUS_UPDATED", None)
            _auto_update()

        mock_execv.assert_called_once()

    def test_auto_update_passes_timeout_to_pull(self):
        """The git pull call must include a timeout parameter."""
        _auto_update = self._import_auto_update()

        pull_kwargs = {}

        def fake_run(cmd, **kw):
            if "rev-parse" in cmd:
                return _make_completed(cmd, stdout="abc123\n")
            if cmd == ["git", "remote"]:
                return _make_completed(cmd, stdout="origin\n")
            if "pull" in cmd:
                pull_kwargs.update(kw)
                return _make_completed(cmd, stdout="Already up to date.\n")
            return _make_completed(cmd)

        with patch.dict(os.environ, {}, clear=False), \
             patch("nexus._legacy_main.subprocess.run", side_effect=fake_run):
            os.environ.pop("_NEXUS_UPDATED", None)
            _auto_update()

        self.assertIn("timeout", pull_kwargs,
                      "git pull subprocess.run must have a timeout parameter")
        self.assertGreater(pull_kwargs["timeout"], 0)


class TestSyncTimeout(unittest.TestCase):
    """Sync functions must not hang on slow git push/pull."""

    def test_pull_rebase_handles_timeout(self):
        """pull_rebase must handle TimeoutExpired from git pull."""
        from nexus.sync import pull_rebase

        def fake_run(cmd, **kw):
            if "remote" in cmd:
                return _make_completed(cmd, stdout="origin\n")
            if "pull" in cmd:
                raise subprocess.TimeoutExpired(cmd, kw.get("timeout", 15))
            if "rebase" in cmd and "--abort" in cmd:
                return _make_completed(cmd)
            return _make_completed(cmd)

        with patch("nexus.sync.subprocess.run", side_effect=fake_run):
            ok, msg = pull_rebase("/fake/repo")

        self.assertFalse(ok)
        self.assertIn("timeout", msg.lower())

    def test_commit_and_push_handles_push_timeout(self):
        """_commit_and_push must handle timeout on git push."""
        from nexus.sync import _commit_and_push

        def fake_run(cmd, **kw):
            if "remote" in cmd:
                return _make_completed(cmd, stdout="origin\n")
            if "status" in cmd and "--porcelain" in cmd:
                return _make_completed(cmd, stdout="M data/projects.yml\n")
            if "add" in cmd:
                return _make_completed(cmd)
            if "diff" in cmd and "--cached" in cmd:
                return _make_completed(cmd, returncode=1)
            if "commit" in cmd:
                return _make_completed(cmd)
            if "push" in cmd:
                raise subprocess.TimeoutExpired(cmd, kw.get("timeout", 15))
            if "pull" in cmd:
                raise subprocess.TimeoutExpired(cmd, kw.get("timeout", 15))
            return _make_completed(cmd)

        with patch("nexus.sync.subprocess.run", side_effect=fake_run):
            result = _commit_and_push("/fake/repo", ["data/projects.yml"], "test")

        self.assertFalse(result)

    def test_pull_rebase_passes_timeout(self):
        """pull_rebase must pass timeout to subprocess.run for git pull."""
        from nexus.sync import pull_rebase

        pull_kwargs = {}

        def fake_run(cmd, **kw):
            if "remote" in cmd:
                return _make_completed(cmd, stdout="origin\n")
            if "pull" in cmd:
                pull_kwargs.update(kw)
                return _make_completed(cmd, stdout="ok\n")
            return _make_completed(cmd)

        with patch("nexus.sync.subprocess.run", side_effect=fake_run):
            pull_rebase("/fake/repo")

        self.assertIn("timeout", pull_kwargs,
                      "git pull in pull_rebase must have timeout")


if __name__ == "__main__":
    unittest.main()
