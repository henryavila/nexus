import json
import nexus
from unittest.mock import patch
from io import StringIO


class TestCmdSkillListPresence:
    def test_shows_presence_column(self, nexus_env):
        from nexus._legacy_main import cmd_skill_list

        # Write data.json with presence (use nexus.DATA_JSON for patched path)
        nexus.DATA_JSON.parent.mkdir(parents=True, exist_ok=True)
        nexus.DATA_JSON.write_text(json.dumps({
            "version": "3.0",
            "skills": {
                "superpowers": {"title": "superpowers", "url": None, "presence": {"ULTRON": {"global": True}}},
            },
            "projects": [], "apps": [], "environments": [], "ideas": [], "codex": [],
        }))

        with patch("sys.stdout", new_callable=StringIO) as out:
            cmd_skill_list()
        output = out.getvalue()
        assert "superpowers" in output
        assert "ULTRON" in output


class TestCmdSkillAddNoScope:
    def test_no_scope_prompt(self, nexus_env, mock_input):
        from nexus._legacy_main import cmd_skill_add

        mock_input.side_effect = ["My Skill", "https://example.com"]
        cmd_skill_add()

        from nexus.skills import load_skills
        skills = load_skills()
        assert len(skills) == 1
        assert skills[0].title == "My Skill"
        assert skills[0].scope == "global"  # default, not prompted


class TestCmdSkillGaps:
    def test_absence_gap(self, nexus_env):
        from nexus._legacy_main import cmd_skill_gaps

        nexus.DATA_JSON.parent.mkdir(parents=True, exist_ok=True)
        nexus.DATA_JSON.write_text(json.dumps({
            "version": "3.0",
            "skills": {
                "pest-testing": {"title": "pest-testing", "url": None, "presence": {
                    "ULTRON": {"global": False, "repos": ["sda"]},
                }},
            },
            "environments": [
                {"hostname": "ULTRON", "name": "ULTRON", "location": "casa", "last_seen": "2026-03-21"},
                {"hostname": "CRCMG", "name": "CRCMG", "location": "trabalho", "last_seen": "2026-03-18"},
            ],
            "projects": [], "apps": [], "ideas": [], "codex": [],
        }))

        with patch("sys.stdout", new_callable=StringIO) as out:
            cmd_skill_gaps()
        output = out.getvalue()
        assert "pest-testing" in output
        assert "CRCMG" in output

    def test_no_gaps(self, nexus_env):
        from nexus._legacy_main import cmd_skill_gaps

        nexus.DATA_JSON.parent.mkdir(parents=True, exist_ok=True)
        nexus.DATA_JSON.write_text(json.dumps({
            "version": "3.0",
            "skills": {
                "sp": {"title": "sp", "url": None, "presence": {
                    "A": {"global": True}, "B": {"global": True},
                }},
            },
            "environments": [
                {"hostname": "A", "name": "A", "location": "x", "last_seen": ""},
                {"hostname": "B", "name": "B", "location": "y", "last_seen": ""},
            ],
            "projects": [], "apps": [], "ideas": [], "codex": [],
        }))

        with patch("sys.stdout", new_callable=StringIO) as out:
            cmd_skill_gaps()
        output = out.getvalue()
        assert "atualizados" in output.lower() or "gaps" not in output.lower()

    def test_coverage_gap(self, nexus_env):
        """Skill global in one env, repo-only in another → coverage gap."""
        from nexus._legacy_main import cmd_skill_gaps

        nexus.DATA_JSON.parent.mkdir(parents=True, exist_ok=True)
        nexus.DATA_JSON.write_text(json.dumps({
            "version": "3.0",
            "skills": {
                "bmad": {"title": "bmad", "url": None, "presence": {
                    "ULTRON": {"global": True},
                    "CRCMG": {"global": False, "repos": ["sda-v2"]},
                }},
            },
            "environments": [
                {"hostname": "ULTRON", "name": "ULTRON", "location": "casa", "last_seen": "2026-03-21"},
                {"hostname": "CRCMG", "name": "CRCMG", "location": "trabalho", "last_seen": "2026-03-18"},
            ],
            "projects": [], "apps": [], "ideas": [], "codex": [],
        }))

        with patch("sys.stdout", new_callable=StringIO) as out:
            cmd_skill_gaps()
        output = out.getvalue()
        assert "bmad" in output
        assert "global" in output.lower()
        assert "CRCMG" in output

    def test_manual_skill_no_gap(self, nexus_env):
        from nexus._legacy_main import cmd_skill_gaps

        nexus.DATA_JSON.parent.mkdir(parents=True, exist_ok=True)
        nexus.DATA_JSON.write_text(json.dumps({
            "version": "3.0",
            "skills": {
                "manual": {"title": "manual", "url": None, "presence": {}},
            },
            "environments": [
                {"hostname": "A", "name": "A", "location": "x", "last_seen": ""},
            ],
            "projects": [], "apps": [], "ideas": [], "codex": [],
        }))

        with patch("sys.stdout", new_callable=StringIO) as out:
            cmd_skill_gaps()
        output = out.getvalue()
        assert "manual" not in output


class TestCmdSkillListMixed:
    def test_shows_global_and_repo_presence(self, nexus_env):
        """cmd_skill_list shows both global and repo presence info."""
        from nexus._legacy_main import cmd_skill_list

        nexus.DATA_JSON.parent.mkdir(parents=True, exist_ok=True)
        nexus.DATA_JSON.write_text(json.dumps({
            "version": "3.0",
            "skills": {
                "sp": {"title": "sp", "url": None, "presence": {
                    "A": {"global": True},
                    "B": {"global": False, "repos": ["proj-x"]},
                }},
            },
            "projects": [], "apps": [], "environments": [], "ideas": [], "codex": [],
        }))

        with patch("sys.stdout", new_callable=StringIO) as out:
            cmd_skill_list()
        output = out.getvalue()
        assert "proj-x" in output


class TestPrintEnvDetailSkills:
    def test_shows_skills_for_env(self, nexus_env):
        from nexus._legacy_main import _print_env_detail
        from nexus.environment import EnvironmentEntry

        nexus.DATA_JSON.parent.mkdir(parents=True, exist_ok=True)
        nexus.DATA_JSON.write_text(json.dumps({
            "version": "3.0",
            "skills": {
                "superpowers": {"title": "superpowers", "url": None, "presence": {"MYHOST": {"global": True}}},
                "other": {"title": "other", "url": None, "presence": {"OTHERHOST": {"global": True}}},
            },
            "projects": [], "apps": [], "environments": [], "ideas": [], "codex": [],
        }))

        env = EnvironmentEntry(hostname="MYHOST", name="My PC", location="casa")

        with patch("sys.stdout", new_callable=StringIO) as out, \
             patch("nexus._legacy_main.get_current_hostname", return_value="MYHOST"):
            _print_env_detail(env)
        output = out.getvalue()
        assert "superpowers" in output
        assert "other" not in output

    def test_shows_repo_skills_for_env(self, nexus_env):
        from nexus._legacy_main import _print_env_detail
        from nexus.environment import EnvironmentEntry

        nexus.DATA_JSON.parent.mkdir(parents=True, exist_ok=True)
        nexus.DATA_JSON.write_text(json.dumps({
            "version": "3.0",
            "skills": {
                "pest": {"title": "pest", "url": None, "presence": {
                    "MYHOST": {"global": False, "repos": ["proj-x"]},
                }},
            },
            "projects": [], "apps": [], "environments": [], "ideas": [], "codex": [],
        }))

        env = EnvironmentEntry(hostname="MYHOST", name="My PC", location="casa")

        with patch("sys.stdout", new_callable=StringIO) as out, \
             patch("nexus._legacy_main.get_current_hostname", return_value="MYHOST"):
            _print_env_detail(env)
        output = out.getvalue()
        assert "pest" in output
        assert "proj-x" in output
