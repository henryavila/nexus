import json
import nexus
import pytest
from io import StringIO
from unittest.mock import patch

from nexus.skills import SkillEntry, save_skill_entry, load_skills


class TestCmdSkillList:
    def test_list_shows_skills(self, nexus_env, capsys):
        """cmd_skill_list reads from data.json (with presence) + load_skills."""
        from nexus._legacy_main import cmd_skill_list

        # Write data.json with presence-based skills
        # IMPORTANT: use nexus.DATA_JSON (dynamic access) to get the patched path
        nexus.DATA_JSON.parent.mkdir(parents=True, exist_ok=True)
        nexus.DATA_JSON.write_text(json.dumps({
            "version": "3.0",
            "skills": {
                "superpowers": {"title": "superpowers", "url": None, "presence": {"H": {"global": True}}},
                "bmad": {"title": "bmad", "url": None, "presence": {"H": {"global": False, "repos": ["proj"]}}},
            },
            "projects": [], "apps": [], "environments": [], "ideas": [], "codex": [],
        }))

        cmd_skill_list()
        output = capsys.readouterr().out
        assert "superpowers" in output
        assert "bmad" in output

    def test_list_empty(self, nexus_env, capsys):
        from nexus._legacy_main import cmd_skill_list
        cmd_skill_list()
        output = capsys.readouterr().out
        assert "nenhum" in output.lower()


class TestCmdSkillAdd:
    def test_add_skill(self, nexus_env, mock_input):
        """cmd_skill_add takes 2 inputs (title, url) — no scope prompt."""
        from nexus._legacy_main import cmd_skill_add
        mock_input.side_effect = ["superpowers", "https://github.com/example"]
        cmd_skill_add()
        skills = load_skills()
        assert len(skills) == 1
        assert skills[0].slug == "superpowers"
