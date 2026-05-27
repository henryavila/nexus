import tempfile
import unittest
from pathlib import Path

from nexus.hooks import HOOK_END, HOOK_START, install_git_hook, remove_git_hook


class HooksBehaviorTests(unittest.TestCase):
    def test_install_is_idempotent_and_preserves_existing_content(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            hooks_dir = root / ".git" / "hooks"
            hooks_dir.mkdir(parents=True)
            hook_file = hooks_dir / "post-commit"
            hook_file.write_text("#!/usr/bin/env bash\necho custom\n", encoding="utf-8")

            self.assertTrue(install_git_hook(str(root)))
            self.assertFalse(install_git_hook(str(root)))  # already installed

            text = hook_file.read_text(encoding="utf-8")
            self.assertIn("echo custom", text)
            self.assertEqual(text.count(HOOK_START), 1)
            self.assertEqual(text.count(HOOK_END), 1)

    def test_remove_only_removes_nexus_block(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            hooks_dir = root / ".git" / "hooks"
            hooks_dir.mkdir(parents=True)
            hook_file = hooks_dir / "post-commit"
            hook_file.write_text("#!/usr/bin/env bash\necho custom\n", encoding="utf-8")

            install_git_hook(str(root))
            removed = remove_git_hook(str(root))

            self.assertTrue(removed)
            text = hook_file.read_text(encoding="utf-8")
            self.assertIn("echo custom", text)
            self.assertNotIn(HOOK_START, text)
            self.assertNotIn(HOOK_END, text)


if __name__ == "__main__":
    unittest.main()
