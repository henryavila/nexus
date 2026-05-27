import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nexus.registry import normalize_path
from nexus.scanner import _check_claude_memory


class TestCheckClaudeMemory(unittest.TestCase):
    """_check_claude_memory detects portable memory by looking for memory
    files/dirs inside the project.

    .claude/memory/ is excluded (Claude Code artifact).
    Portable markers: MEMORY.md, MEMORIA.md (anywhere, excluding .claude/),
    and dirs named memory, memoria, .memory at project root.
    """

    def test_dot_claude_memory_dir_is_NOT_portable(self):
        """'.claude/memory/' is a Claude Code artifact — not portable."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / ".claude" / "memory").mkdir(parents=True)
            (root / ".claude" / "memory" / "MEMORY.md").write_text("# mem")
            fake_home = Path(td) / "fakehome"
            fake_home.mkdir()
            with patch("nexus.scanner.Path.home", return_value=fake_home):
                self.assertIsNone(_check_claude_memory(root))

    def test_dot_claude_memory_with_local_is_local_only(self):
        """'.claude/memory/' artifact + local ~/.claude → local-only (False)."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / ".claude" / "memory").mkdir(parents=True)
            (root / ".claude" / "memory" / "MEMORY.md").write_text("# mem")
            fake_home = Path(td) / "fakehome"
            encoded = str(root).replace("/", "-").replace(" ", "-")
            mem_dir = fake_home / ".claude" / "projects" / encoded / "memory"
            mem_dir.mkdir(parents=True)
            (mem_dir / "MEMORY.md").write_text("# mem")
            with patch("nexus.scanner.Path.home", return_value=fake_home):
                self.assertFalse(_check_claude_memory(root))

    def test_local_symlink_into_project_is_portable(self):
        """~/.claude/projects/{encoded}/memory → symlink to project = portable."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            # Create .claude/memory inside project (target of symlink)
            (root / ".claude" / "memory").mkdir(parents=True)
            (root / ".claude" / "memory" / "MEMORY.md").write_text("# mem")
            fake_home = Path(td) / "fakehome"
            # Use normalize_path to match what _check_claude_memory computes
            # (on macOS, /var/... resolves to /private/var/...)
            encoded = normalize_path(str(root)).replace("/", "-").replace(" ", "-")
            sym_parent = fake_home / ".claude" / "projects" / encoded
            sym_parent.mkdir(parents=True)
            # Symlink ~/.claude/projects/{encoded}/memory → project/.claude/memory
            os.symlink(str(root / ".claude" / "memory"), str(sym_parent / "memory"))
            with patch("nexus.scanner.Path.home", return_value=fake_home):
                self.assertTrue(_check_claude_memory(root))

    def test_local_symlink_outside_project_is_local_only(self):
        """~/.claude/projects/{encoded}/memory → symlink to elsewhere = local-only."""
        with tempfile.TemporaryDirectory() as td1, tempfile.TemporaryDirectory() as td2:
            root = Path(td1) / "myproject"
            root.mkdir()
            fake_home = Path(td1) / "fakehome"
            encoded = str(root).replace("/", "-").replace(" ", "-")
            sym_parent = fake_home / ".claude" / "projects" / encoded
            sym_parent.mkdir(parents=True)
            # Symlink to somewhere completely outside the project
            external = Path(td2) / "external_memory"
            external.mkdir()
            os.symlink(str(external), str(sym_parent / "memory"))
            with patch("nexus.scanner.Path.home", return_value=fake_home):
                self.assertFalse(_check_claude_memory(root))

    def test_memory_md_anywhere_in_project_is_portable(self):
        """e.g. Lucio Monteiro Kids: memoria/MEMORY.md"""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "memoria").mkdir()
            (root / "memoria" / "MEMORY.md").write_text("# mem")
            self.assertTrue(_check_claude_memory(root))

    def test_memoria_md_deep_in_project_is_portable(self):
        """e.g. CRCMG: 98-Base-Conhecimento/agente/MEMORIA.md"""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            deep = root / "base" / "agente"
            deep.mkdir(parents=True)
            (deep / "MEMORIA.md").write_text("# mem")
            self.assertTrue(_check_claude_memory(root))

    def test_dot_memory_dir_is_portable(self):
        """e.g. IASD: .memory/ directory"""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / ".memory").mkdir()
            (root / ".memory" / "treasury.md").write_text("# area mem")
            self.assertTrue(_check_claude_memory(root))

    def test_memory_dir_at_root_is_portable(self):
        """e.g. mnemo: MEMORY/ directory at root"""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "MEMORY").mkdir()
            self.assertTrue(_check_claude_memory(root))

    def test_claude_md_alone_is_not_portable(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "CLAUDE.md").write_text("# instructions")
            fake_home = Path(td) / "fakehome"
            fake_home.mkdir()
            with patch("nexus.scanner.Path.home", return_value=fake_home):
                self.assertIsNone(_check_claude_memory(root))

    def test_local_only_returns_false(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            fake_home = Path(td) / "fakehome"
            encoded = str(root).replace("/", "-").replace(" ", "-")
            mem_dir = fake_home / ".claude" / "projects" / encoded / "memory"
            mem_dir.mkdir(parents=True)
            (mem_dir / "MEMORY.md").write_text("# mem")
            with patch("nexus.scanner.Path.home", return_value=fake_home):
                self.assertFalse(_check_claude_memory(root))

    def test_no_memory_anywhere_returns_none(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            fake_home = Path(td) / "fakehome"
            fake_home.mkdir()
            with patch("nexus.scanner.Path.home", return_value=fake_home):
                self.assertIsNone(_check_claude_memory(root))

    def test_portable_takes_priority_over_local(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / ".memory").mkdir()
            (root / ".memory" / "area.md").write_text("# mem")
            fake_home = Path(td) / "fakehome"
            encoded = str(root).replace("/", "-").replace(" ", "-")
            mem_dir = fake_home / ".claude" / "projects" / encoded / "memory"
            mem_dir.mkdir(parents=True)
            with patch("nexus.scanner.Path.home", return_value=fake_home):
                self.assertTrue(_check_claude_memory(root))


if __name__ == "__main__":
    unittest.main()
