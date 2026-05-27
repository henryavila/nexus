import json
import pytest
from pathlib import Path
from unittest.mock import patch


class TestDetectSkillsForScan:
    """Tests for detect_skills_for_scan."""

    def test_global_plugins_detected(self, tmp_path):
        """Enabled plugins from settings.json are detected as global."""
        from nexus.skills import detect_skills_for_scan

        settings = {"enabledPlugins": {
            "superpowers@claude-plugins-official": True,
            "bmad@some-marketplace": True,
        }}
        settings_path = tmp_path / "settings.json"
        settings_path.write_text(json.dumps(settings))

        result = detect_skills_for_scan(
            projects=[], existing_skills={}, hostname="TESTHOST",
            settings_path=settings_path,
        )
        assert "superpowers" in result
        assert result["superpowers"]["presence"]["TESTHOST"]["global"] is True
        assert "bmad" in result
        assert result["bmad"]["presence"]["TESTHOST"]["global"] is True

    def test_disabled_plugins_excluded(self, tmp_path):
        """Plugins with value false are not detected."""
        from nexus.skills import detect_skills_for_scan

        settings = {"enabledPlugins": {
            "superpowers@official": True,
            "disabled@official": False,
        }}
        settings_path = tmp_path / "settings.json"
        settings_path.write_text(json.dumps(settings))

        result = detect_skills_for_scan(
            projects=[], existing_skills={}, hostname="TESTHOST",
            settings_path=settings_path,
        )
        assert "superpowers" in result
        assert "disabled" not in result

    def test_no_settings_file(self, tmp_path):
        """Missing settings.json produces no global skills."""
        from nexus.skills import detect_skills_for_scan

        result = detect_skills_for_scan(
            projects=[], existing_skills={}, hostname="TESTHOST",
            settings_path=tmp_path / "nonexistent.json",
        )
        assert result == {}

    def test_slug_extraction(self, tmp_path):
        """Slug is part before @ in plugin key."""
        from nexus.skills import detect_skills_for_scan

        settings = {"enabledPlugins": {"ui-ux-pro-max@ui-ux-pro-max-skill": True}}
        settings_path = tmp_path / "settings.json"
        settings_path.write_text(json.dumps(settings))

        result = detect_skills_for_scan(
            projects=[], existing_skills={}, hostname="H",
            settings_path=settings_path,
        )
        assert "ui-ux-pro-max" in result

    # --- Task 2: Repo detection, grouping, dedup ---

    def test_repo_skills_from_agents_dir(self, tmp_path):
        """Skills in .agents/skills/ are detected as repo skills."""
        from nexus.skills import detect_skills_for_scan

        proj_root = tmp_path / "myproject"
        agents = proj_root / ".agents" / "skills"
        agents.mkdir(parents=True)
        (agents / "check").mkdir()
        (agents / "publish").mkdir()

        settings_path = tmp_path / "settings.json"
        settings_path.write_text("{}")

        projects = [{"slug": "myproject", "path": str(proj_root)}]
        with patch("nexus.environment.resolve_path_for_entry", return_value=str(proj_root)), \
             patch("nexus.project_config.resolve_project_path", return_value=str(proj_root)):
            result = detect_skills_for_scan(
                projects=projects, existing_skills={}, hostname="HOST",
                settings_path=settings_path,
            )
        assert "check" in result
        assert result["check"]["presence"]["HOST"] == {"global": False, "repos": ["myproject"]}
        assert "publish" in result

    def test_agents_grouping_threshold(self, tmp_path):
        """3+ entries with same prefix are grouped into one skill."""
        from nexus.skills import detect_skills_for_scan

        proj_root = tmp_path / "proj"
        agents = proj_root / ".agents" / "skills"
        agents.mkdir(parents=True)
        for name in ["bmad-agent-dev", "bmad-agent-qa", "bmad-agent-pm"]:
            (agents / name).mkdir()

        settings_path = tmp_path / "settings.json"
        settings_path.write_text("{}")

        projects = [{"slug": "proj", "path": str(proj_root)}]
        with patch("nexus.environment.resolve_path_for_entry", return_value=str(proj_root)), \
             patch("nexus.project_config.resolve_project_path", return_value=str(proj_root)):
            result = detect_skills_for_scan(
                projects=projects, existing_skills={}, hostname="H",
                settings_path=settings_path,
            )
        assert "bmad" in result
        assert "bmad-agent-dev" not in result

    def test_agents_below_threshold_keeps_full_name(self, tmp_path):
        """< 3 entries with same prefix keep full name."""
        from nexus.skills import detect_skills_for_scan

        proj_root = tmp_path / "proj"
        agents = proj_root / ".agents" / "skills"
        agents.mkdir(parents=True)
        (agents / "pest-testing").mkdir()
        (agents / "tailwindcss-dev").mkdir()

        settings_path = tmp_path / "settings.json"
        settings_path.write_text("{}")

        projects = [{"slug": "proj", "path": str(proj_root)}]
        with patch("nexus.environment.resolve_path_for_entry", return_value=str(proj_root)), \
             patch("nexus.project_config.resolve_project_path", return_value=str(proj_root)):
            result = detect_skills_for_scan(
                projects=projects, existing_skills={}, hostname="H",
                settings_path=settings_path,
            )
        assert "pest-testing" in result
        assert "tailwindcss-dev" in result
        assert "pest" not in result

    def test_global_dedup_skips_repo(self, tmp_path):
        """Global skill is not duplicated as repo skill."""
        from nexus.skills import detect_skills_for_scan

        proj_root = tmp_path / "proj"
        agents = proj_root / ".agents" / "skills"
        agents.mkdir(parents=True)
        (agents / "superpowers").mkdir()

        settings = {"enabledPlugins": {"superpowers@official": True}}
        settings_path = tmp_path / "settings.json"
        settings_path.write_text(json.dumps(settings))

        projects = [{"slug": "proj", "path": str(proj_root)}]
        with patch("nexus.environment.resolve_path_for_entry", return_value=str(proj_root)), \
             patch("nexus.project_config.resolve_project_path", return_value=str(proj_root)):
            result = detect_skills_for_scan(
                projects=projects, existing_skills={}, hostname="H",
                settings_path=settings_path,
            )
        assert result["superpowers"]["presence"]["H"]["global"] is True
        assert "repos" not in result["superpowers"]["presence"]["H"]

    def test_claude_skills_below_threshold(self, tmp_path):
        """Skills in .claude/skills/ below grouping threshold stay individual."""
        from nexus.skills import detect_skills_for_scan

        proj_root = tmp_path / "proj"
        claude_skills = proj_root / ".claude" / "skills"
        claude_skills.mkdir(parents=True)
        (claude_skills / "check").mkdir()
        (claude_skills / "create-migration").mkdir()

        settings_path = tmp_path / "settings.json"
        settings_path.write_text("{}")

        projects = [{"slug": "proj", "path": str(proj_root)}]
        with patch("nexus.environment.resolve_path_for_entry", return_value=str(proj_root)), \
             patch("nexus.project_config.resolve_project_path", return_value=str(proj_root)):
            result = detect_skills_for_scan(
                projects=projects, existing_skills={}, hostname="H",
                settings_path=settings_path,
            )
        assert "check" in result
        assert "create-migration" in result

    def test_claude_skills_grouped_above_threshold(self, tmp_path):
        """Skills in .claude/skills/ with 3+ same prefix are grouped."""
        from nexus.skills import detect_skills_for_scan

        proj_root = tmp_path / "proj"
        claude_skills = proj_root / ".claude" / "skills"
        claude_skills.mkdir(parents=True)
        for name in ["bmad-agent-dev", "bmad-agent-qa", "bmad-agent-pm", "bmad-workflows"]:
            (claude_skills / name).mkdir()

        settings_path = tmp_path / "settings.json"
        settings_path.write_text("{}")

        projects = [{"slug": "proj", "path": str(proj_root)}]
        with patch("nexus.environment.resolve_path_for_entry", return_value=str(proj_root)), \
             patch("nexus.project_config.resolve_project_path", return_value=str(proj_root)):
            result = detect_skills_for_scan(
                projects=projects, existing_skills={}, hostname="H",
                settings_path=settings_path,
            )
        assert "bmad" in result
        assert "bmad-agent-dev" not in result
        assert "bmad-workflows" not in result

    def test_agents_claude_dedup_same_repo(self, tmp_path):
        """.agents/ and .claude/ same slug counted once."""
        from nexus.skills import detect_skills_for_scan

        proj_root = tmp_path / "proj"
        (proj_root / ".agents" / "skills" / "pest-testing").mkdir(parents=True)
        (proj_root / ".claude" / "skills" / "pest-testing").mkdir(parents=True)

        settings_path = tmp_path / "settings.json"
        settings_path.write_text("{}")

        projects = [{"slug": "proj", "path": str(proj_root)}]
        with patch("nexus.environment.resolve_path_for_entry", return_value=str(proj_root)), \
             patch("nexus.project_config.resolve_project_path", return_value=str(proj_root)):
            result = detect_skills_for_scan(
                projects=projects, existing_skills={}, hostname="H",
                settings_path=settings_path,
            )
        assert result["pest-testing"]["presence"]["H"]["repos"] == ["proj"]

    def test_project_without_path_skipped(self, tmp_path):
        """Projects with no resolvable path are skipped."""
        from nexus.skills import detect_skills_for_scan

        settings_path = tmp_path / "settings.json"
        settings_path.write_text("{}")

        projects = [{"slug": "ghost", "path": "/nonexistent"}]
        with patch("nexus.environment.resolve_path_for_entry", return_value=None):
            result = detect_skills_for_scan(
                projects=projects, existing_skills={}, hostname="H",
                settings_path=settings_path,
            )
        assert result == {}

    def test_plugin_key_without_at(self, tmp_path):
        """Plugin key without @ uses full key as slug."""
        from nexus.skills import detect_skills_for_scan

        settings = {"enabledPlugins": {"my-custom-plugin": True}}
        settings_path = tmp_path / "settings.json"
        settings_path.write_text(json.dumps(settings))

        result = detect_skills_for_scan(
            projects=[], existing_skills={}, hostname="H",
            settings_path=settings_path,
        )
        assert "my-custom-plugin" in result
        assert result["my-custom-plugin"]["presence"]["H"]["global"] is True

    def test_agents_dir_ignores_files(self, tmp_path):
        """.agents/skills/ ignores non-directory entries like .DS_Store."""
        from nexus.skills import detect_skills_for_scan

        proj_root = tmp_path / "proj"
        agents = proj_root / ".agents" / "skills"
        agents.mkdir(parents=True)
        (agents / "real-skill").mkdir()
        (agents / ".DS_Store").write_text("")  # file, not dir

        settings_path = tmp_path / "settings.json"
        settings_path.write_text("{}")

        projects = [{"slug": "proj", "path": str(proj_root)}]
        with patch("nexus.environment.resolve_path_for_entry", return_value=str(proj_root)), \
             patch("nexus.project_config.resolve_project_path", return_value=str(proj_root)):
            result = detect_skills_for_scan(
                projects=projects, existing_skills={}, hostname="H",
                settings_path=settings_path,
            )
        assert "real-skill" in result
        assert ".DS_Store" not in result

    # --- Task 3: Merge logic ---

    def test_preserves_other_hostname_presence(self, tmp_path):
        """Scan preserves presence data from other hostnames."""
        from nexus.skills import detect_skills_for_scan

        settings = {"enabledPlugins": {"superpowers@official": True}}
        settings_path = tmp_path / "settings.json"
        settings_path.write_text(json.dumps(settings))

        existing = {
            "superpowers": {
                "title": "superpowers",
                "url": "https://example.com",
                "presence": {"OTHER-HOST": {"global": True}},
            }
        }
        result = detect_skills_for_scan(
            projects=[], existing_skills=existing, hostname="LOCAL",
            settings_path=settings_path,
        )
        assert result["superpowers"]["presence"]["OTHER-HOST"]["global"] is True
        assert result["superpowers"]["presence"]["LOCAL"]["global"] is True
        # Preserves existing title/url
        assert result["superpowers"]["url"] == "https://example.com"

    def test_preserves_existing_title_url(self, tmp_path):
        """Auto-detected skill preserves title/url from existing data."""
        from nexus.skills import detect_skills_for_scan

        settings = {"enabledPlugins": {"superpowers@official": True}}
        settings_path = tmp_path / "settings.json"
        settings_path.write_text(json.dumps(settings))

        existing = {
            "superpowers": {"title": "Superpowers Plugin", "url": "https://sp.dev", "presence": {}},
        }
        result = detect_skills_for_scan(
            projects=[], existing_skills=existing, hostname="H",
            settings_path=settings_path,
        )
        assert result["superpowers"]["title"] == "Superpowers Plugin"
        assert result["superpowers"]["url"] == "https://sp.dev"

    def test_multi_project_same_skill(self, tmp_path):
        """Same repo skill in multiple projects listed in repos array."""
        from nexus.skills import detect_skills_for_scan

        proj_a = tmp_path / "proj-a"
        proj_b = tmp_path / "proj-b"
        for p in [proj_a, proj_b]:
            (p / ".claude" / "skills" / "check").mkdir(parents=True)

        settings_path = tmp_path / "settings.json"
        settings_path.write_text("{}")

        projects = [
            {"slug": "proj-a", "path": str(proj_a)},
            {"slug": "proj-b", "path": str(proj_b)},
        ]
        with patch("nexus.environment.resolve_path_for_entry", side_effect=lambda s, p: p), \
             patch("nexus.project_config.resolve_project_path", side_effect=lambda p: p):
            result = detect_skills_for_scan(
                projects=projects, existing_skills={}, hostname="H",
                settings_path=settings_path,
            )
        assert sorted(result["check"]["presence"]["H"]["repos"]) == ["proj-a", "proj-b"]


    def test_corrupt_settings_json(self, tmp_path):
        """Corrupt settings.json is handled gracefully."""
        from nexus.skills import detect_skills_for_scan

        settings_path = tmp_path / "settings.json"
        settings_path.write_text("{invalid json")

        result = detect_skills_for_scan(
            projects=[], existing_skills={}, hostname="H",
            settings_path=settings_path,
        )
        assert result == {}

    def test_project_without_slug(self, tmp_path):
        """Project dict with empty slug is skipped."""
        from nexus.skills import detect_skills_for_scan

        settings_path = tmp_path / "settings.json"
        settings_path.write_text("{}")

        result = detect_skills_for_scan(
            projects=[{"slug": "", "path": "/tmp"}], existing_skills={}, hostname="H",
            settings_path=settings_path,
        )
        assert result == {}

    def test_project_path_not_exists(self, tmp_path):
        """Project whose resolved path doesn't exist is skipped."""
        from nexus.skills import detect_skills_for_scan

        settings_path = tmp_path / "settings.json"
        settings_path.write_text("{}")

        projects = [{"slug": "proj", "path": "/nonexistent"}]
        with patch("nexus.environment.resolve_path_for_entry", return_value="/nonexistent"), \
             patch("nexus.project_config.resolve_project_path", return_value="/nonexistent-really"):
            result = detect_skills_for_scan(
                projects=projects, existing_skills={}, hostname="H",
                settings_path=settings_path,
            )
        assert result == {}

    def test_repo_skill_cross_host(self, tmp_path):
        """Repo skill detected adds new host entry when skill exists from other host."""
        from nexus.skills import detect_skills_for_scan

        proj_root = tmp_path / "proj"
        (proj_root / ".claude" / "skills" / "my-tool").mkdir(parents=True)

        settings_path = tmp_path / "settings.json"
        settings_path.write_text("{}")

        existing = {
            "my-tool": {
                "title": "my-tool", "url": None,
                "presence": {"OTHER": {"global": False, "repos": ["other-proj"]}},
            }
        }

        projects = [{"slug": "proj", "path": str(proj_root)}]
        with patch("nexus.environment.resolve_path_for_entry", return_value=str(proj_root)), \
             patch("nexus.project_config.resolve_project_path", return_value=str(proj_root)):
            result = detect_skills_for_scan(
                projects=projects, existing_skills=existing, hostname="LOCAL",
                settings_path=settings_path,
            )
        # Should have both hosts
        assert "OTHER" in result["my-tool"]["presence"]
        assert "LOCAL" in result["my-tool"]["presence"]
        assert result["my-tool"]["presence"]["LOCAL"] == {"global": False, "repos": ["proj"]}

    def test_repo_skill_multi_project_cross_host_existing(self, tmp_path):
        """Repo skill from multiple projects where existing entry has other host
        exercises the _add_repo_presence else branch (line 323)."""
        from nexus.skills import detect_skills_for_scan

        proj_a = tmp_path / "proj-a"
        proj_b = tmp_path / "proj-b"
        (proj_a / ".claude" / "skills" / "shared").mkdir(parents=True)
        (proj_b / ".claude" / "skills" / "shared").mkdir(parents=True)

        settings_path = tmp_path / "settings.json"
        settings_path.write_text("{}")

        # shared exists in detected from proj-a (host=LOCAL), then proj-b also has it
        # But we also need the OTHER host path: existing has OTHER host presence
        existing = {
            "shared": {
                "title": "shared", "url": None,
                "presence": {"OTHER": {"global": False, "repos": ["x"]}},
            }
        }

        projects = [
            {"slug": "proj-a", "path": str(proj_a)},
            {"slug": "proj-b", "path": str(proj_b)},
        ]
        with patch("nexus.environment.resolve_path_for_entry", side_effect=lambda s, p: p), \
             patch("nexus.project_config.resolve_project_path", side_effect=lambda p: p):
            result = detect_skills_for_scan(
                projects=projects, existing_skills=existing, hostname="LOCAL",
                settings_path=settings_path,
            )
        # LOCAL should have both repos
        assert sorted(result["shared"]["presence"]["LOCAL"]["repos"]) == ["proj-a", "proj-b"]
        # OTHER should be preserved
        assert "OTHER" in result["shared"]["presence"]


class TestAddRepoPresence:
    """Tests for _add_repo_presence helper."""

    def test_adds_new_hostname_to_existing_skill(self):
        """When skill exists in detected but for a different hostname, adds new host."""
        from nexus.skills import _add_repo_presence

        detected = {
            "my-tool": {
                "title": "my-tool", "url": None,
                "presence": {"OTHER": {"global": False, "repos": ["proj-x"]}},
            }
        }
        _add_repo_presence(detected, {}, "my-tool", "local-proj", "LOCAL")
        assert detected["my-tool"]["presence"]["LOCAL"] == {"global": False, "repos": ["local-proj"]}
        # OTHER host preserved
        assert "OTHER" in detected["my-tool"]["presence"]


class TestGroupAgentsSkills:
    """Tests for _group_agents_skills."""

    def test_empty_dir(self, tmp_path):
        from nexus.skills import _group_agents_skills
        d = tmp_path / "skills"
        d.mkdir()
        assert _group_agents_skills(d) == []

    def test_no_dash_entries(self, tmp_path):
        from nexus.skills import _group_agents_skills
        d = tmp_path / "skills"
        d.mkdir()
        (d / "superpowers").mkdir()
        assert _group_agents_skills(d) == ["superpowers"]

    def test_group_threshold(self, tmp_path):
        from nexus.skills import _group_agents_skills
        d = tmp_path / "skills"
        d.mkdir()
        for n in ["bmad-a", "bmad-b", "bmad-c"]:
            (d / n).mkdir()
        assert _group_agents_skills(d) == ["bmad"]

    def test_below_threshold(self, tmp_path):
        from nexus.skills import _group_agents_skills
        d = tmp_path / "skills"
        d.mkdir()
        (d / "pest-testing").mkdir()
        (d / "css-dev").mkdir()
        result = _group_agents_skills(d)
        assert "pest-testing" in result
        assert "css-dev" in result
        assert "pest" not in result

    def test_package_map_override(self, tmp_path, monkeypatch):
        from nexus.skills import _group_agents_skills, SKILL_PACKAGE_MAP
        d = tmp_path / "skills"
        d.mkdir()
        (d / "custom-a").mkdir()
        (d / "custom-b").mkdir()
        # Without map: custom-a and custom-b stay as-is (< 3 threshold)
        assert "custom-a" in _group_agents_skills(d)
        # With map: both map to "custom", now 2 entries with same prefix
        # Still < 3 so stays ungrouped — but let's add a third
        (d / "custom-c").mkdir()
        monkeypatch.setitem(SKILL_PACKAGE_MAP, "custom-a", "custom")
        monkeypatch.setitem(SKILL_PACKAGE_MAP, "custom-b", "custom")
        monkeypatch.setitem(SKILL_PACKAGE_MAP, "custom-c", "custom")
        result = _group_agents_skills(d)
        assert "custom" in result
        assert "custom-a" not in result


class TestScanAllSkillsIntegration:
    """Integration test: scan_all includes skills with presence."""

    def test_scan_all_includes_skills_presence(self, nexus_env):
        from nexus.scanner import scan_all

        with patch("nexus.scanner.get_current_hostname", return_value="TESTHOST"), \
             patch("nexus.scanner.find_environment", return_value=None), \
             patch("nexus.scanner.update_last_seen"):
            data = scan_all()

        skills = data.get("skills", {})
        # At minimum, skills dict exists (may be empty in test env)
        assert isinstance(skills, dict)
        # Verify no 'scope' key in any skill entry
        for slug, info in skills.items():
            assert "scope" not in info, f"scope should not be in data.json skills: {slug}"
            assert "presence" in info, f"presence missing for {slug}"

    def test_scan_all_preserves_other_host_skills(self, nexus_env):
        """Skills from other hosts not detected locally are preserved."""
        from nexus.scanner import scan_all, _read_data, _write_data
        from nexus import LOCK_FILE, file_lock

        # Pre-populate existing data with a skill from another host
        existing = _read_data()
        existing["skills"] = {
            "remote-only": {
                "title": "remote-only",
                "url": None,
                "presence": {"REMOTE-HOST": {"global": True}},
            }
        }
        with file_lock(LOCK_FILE):
            _write_data(existing)

        with patch("nexus.scanner.get_current_hostname", return_value="LOCAL"), \
             patch("nexus.scanner.find_environment", return_value=None), \
             patch("nexus.scanner.update_last_seen"):
            data = scan_all()

        # remote-only should be preserved (minus LOCAL hostname)
        assert "remote-only" in data["skills"]
        assert "REMOTE-HOST" in data["skills"]["remote-only"]["presence"]
        assert "LOCAL" not in data["skills"]["remote-only"]["presence"]
