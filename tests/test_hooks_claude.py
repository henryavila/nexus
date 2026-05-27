import json
from pathlib import Path

import pytest

from nexus.hooks import (
    CLAUDE_HOOK_CMD,
    CLAUDE_HOOK_MATCHER,
    install_claude_hook,
    remove_claude_hook,
)


class TestInstallClaudeHook:
    def test_installs_hook(self, tmp_path):
        result = install_claude_hook(str(tmp_path))

        assert result is True
        settings_file = tmp_path / ".claude" / "settings.local.json"
        assert settings_file.exists()

        data = json.loads(settings_file.read_text(encoding="utf-8"))
        post_tool = data["hooks"]["PostToolUse"]
        assert len(post_tool) == 1
        entry = post_tool[0]
        assert entry["matcher"] == CLAUDE_HOOK_MATCHER
        assert len(entry["hooks"]) == 1
        assert entry["hooks"][0]["type"] == "command"
        assert entry["hooks"][0]["command"] == CLAUDE_HOOK_CMD

    def test_idempotent(self, tmp_path):
        first = install_claude_hook(str(tmp_path))
        second = install_claude_hook(str(tmp_path))

        assert first is True
        assert second is False

        # File should still be valid with exactly one hook entry
        settings_file = tmp_path / ".claude" / "settings.local.json"
        data = json.loads(settings_file.read_text(encoding="utf-8"))
        post_tool = data["hooks"]["PostToolUse"]
        nexus_entries = [
            e for e in post_tool
            if any("nexus scan" in h.get("command", "") for h in e.get("hooks", []))
        ]
        assert len(nexus_entries) == 1

    def test_preserves_existing_settings(self, tmp_path):
        settings_file = tmp_path / ".claude" / "settings.local.json"
        settings_file.parent.mkdir(parents=True, exist_ok=True)

        existing = {
            "permissions": {"allow": ["Bash(*)", "Read(*)"]},
            "hooks": {
                "PostToolUse": [
                    {
                        "matcher": "SomeOtherTool",
                        "hooks": [{"type": "command", "command": "echo hello"}],
                    }
                ]
            },
        }
        settings_file.write_text(json.dumps(existing, indent=2), encoding="utf-8")

        result = install_claude_hook(str(tmp_path))

        assert result is True
        data = json.loads(settings_file.read_text(encoding="utf-8"))

        # Original permission block preserved
        assert data["permissions"] == {"allow": ["Bash(*)", "Read(*)"]}

        post_tool = data["hooks"]["PostToolUse"]
        # Both the original entry and the new nexus entry are present
        assert len(post_tool) == 2

        matchers = [e["matcher"] for e in post_tool]
        assert "SomeOtherTool" in matchers
        assert CLAUDE_HOOK_MATCHER in matchers

    def test_returns_false_when_root_missing(self, tmp_path):
        nonexistent = tmp_path / "does_not_exist"
        result = install_claude_hook(str(nonexistent))
        assert result is False

    def test_creates_claude_dir_automatically(self, tmp_path):
        # .claude directory does not exist beforehand
        assert not (tmp_path / ".claude").exists()
        install_claude_hook(str(tmp_path))
        assert (tmp_path / ".claude").is_dir()


class TestRemoveClaudeHook:
    def test_removes_hook(self, tmp_path):
        install_claude_hook(str(tmp_path))

        result = remove_claude_hook(str(tmp_path))

        assert result is True
        settings_file = tmp_path / ".claude" / "settings.local.json"
        assert settings_file.exists()

        data = json.loads(settings_file.read_text(encoding="utf-8"))
        # hooks key should be gone entirely when nothing remains
        assert "hooks" not in data

    def test_noop_when_no_file(self, tmp_path):
        result = remove_claude_hook(str(tmp_path))
        assert result is False

    def test_noop_when_no_hook(self, tmp_path):
        settings_file = tmp_path / ".claude" / "settings.local.json"
        settings_file.parent.mkdir(parents=True, exist_ok=True)

        existing = {
            "hooks": {
                "PostToolUse": [
                    {
                        "matcher": "SomeOtherTool",
                        "hooks": [{"type": "command", "command": "echo hello"}],
                    }
                ]
            }
        }
        settings_file.write_text(json.dumps(existing, indent=2), encoding="utf-8")
        original_text = settings_file.read_text(encoding="utf-8")

        result = remove_claude_hook(str(tmp_path))

        assert result is False
        # File content must be byte-for-byte identical (no mutation)
        assert settings_file.read_text(encoding="utf-8") == original_text

    def test_removes_only_nexus_entry_preserves_others(self, tmp_path):
        install_claude_hook(str(tmp_path))

        # Add an extra unrelated entry
        settings_file = tmp_path / ".claude" / "settings.local.json"
        data = json.loads(settings_file.read_text(encoding="utf-8"))
        data["hooks"]["PostToolUse"].append(
            {
                "matcher": "SomeOtherTool",
                "hooks": [{"type": "command", "command": "echo other"}],
            }
        )
        settings_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

        result = remove_claude_hook(str(tmp_path))

        assert result is True
        data = json.loads(settings_file.read_text(encoding="utf-8"))
        post_tool = data["hooks"]["PostToolUse"]
        assert len(post_tool) == 1
        assert post_tool[0]["matcher"] == "SomeOtherTool"

    def test_returns_false_on_invalid_json(self, tmp_path):
        settings_file = tmp_path / ".claude" / "settings.local.json"
        settings_file.parent.mkdir(parents=True, exist_ok=True)
        settings_file.write_text("not valid json {{", encoding="utf-8")

        result = remove_claude_hook(str(tmp_path))

        assert result is False
