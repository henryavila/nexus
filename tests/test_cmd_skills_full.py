"""Tests for cmd_skill_* CLI commands."""

import json
import pytest
from nexus.skills import SkillEntry, save_skill_entry, load_skills


class TestCmdSkillList:
    def test_lists_skills(self, nexus_env, capsys):
        from nexus._legacy_main import cmd_skill_list
        entry = SkillEntry(title="My Skill", slug="my-skill", scope="global")
        save_skill_entry(entry)
        cmd_skill_list()
        out = capsys.readouterr().out
        assert "My Skill" in out
        assert "my-skill" in out

    def test_empty_list(self, nexus_env, capsys):
        from nexus._legacy_main import cmd_skill_list
        cmd_skill_list()
        out = capsys.readouterr().out
        assert "Nenhum" in out


class TestCmdSkillAdd:
    def test_add_skill(self, nexus_env, mock_input):
        from nexus._legacy_main import cmd_skill_add
        mock_input.side_effect = [
            "Test Skill",           # title
            "https://example.com",  # url
        ]
        cmd_skill_add()
        skills = load_skills()
        assert len(skills) == 1
        assert skills[0].title == "Test Skill"
        assert skills[0].slug == "test-skill"
        assert skills[0].url == "https://example.com"

    def test_add_skill_empty_title_aborts(self, nexus_env, mock_input, capsys):
        from nexus._legacy_main import cmd_skill_add
        mock_input.return_value = ""
        cmd_skill_add()
        assert load_skills() == []
        assert "obrigatório" in capsys.readouterr().out

    def test_add_skill_no_url(self, nexus_env, mock_input):
        from nexus._legacy_main import cmd_skill_add
        mock_input.side_effect = [
            "Default Scope Skill",
            "",   # no url
        ]
        cmd_skill_add()
        skills = load_skills()
        assert len(skills) == 1
        assert skills[0].title == "Default Scope Skill"

    def test_add_skill_ctrl_c(self, nexus_env, mock_input, capsys):
        from nexus._legacy_main import cmd_skill_add
        mock_input.side_effect = KeyboardInterrupt
        cmd_skill_add()
        assert load_skills() == []
        assert "Cancelado" in capsys.readouterr().out


class TestCmdSkillEdit:
    def test_edit_opens_editor(self, nexus_env, mock_editor, capsys):
        from nexus._legacy_main import cmd_skill_edit
        entry = SkillEntry(title="Edit Me", slug="edit-me", scope="global")
        save_skill_entry(entry)
        cmd_skill_edit("edit-me")
        out = capsys.readouterr().out
        assert "editado" in out

    def test_edit_not_found(self, nexus_env, mock_editor, capsys):
        from nexus._legacy_main import cmd_skill_edit
        cmd_skill_edit("nonexistent")
        out = capsys.readouterr().out
        assert "não encontrado" in out

    def test_edit_no_editor_configured(self, nexus_env, capsys):
        from unittest.mock import patch
        from nexus._legacy_main import cmd_skill_edit
        entry = SkillEntry(title="No Editor", slug="no-editor", scope="global")
        save_skill_entry(entry)
        with patch("nexus._legacy_main.get_default_editor", return_value=None):
            cmd_skill_edit("no-editor")
        out = capsys.readouterr().out
        assert "editor" in out.lower()


class TestCmdSkillRemove:
    def test_remove_confirmed(self, nexus_env, mock_input, capsys):
        from nexus._legacy_main import cmd_skill_remove
        entry = SkillEntry(title="To Remove", slug="to-remove", scope="global")
        save_skill_entry(entry)
        mock_input.return_value = "s"
        cmd_skill_remove("to-remove")
        assert load_skills() == []
        assert "removido" in capsys.readouterr().out

    def test_remove_cancelled(self, nexus_env, mock_input, capsys):
        from nexus._legacy_main import cmd_skill_remove
        entry = SkillEntry(title="Keep Me", slug="keep-me", scope="global")
        save_skill_entry(entry)
        mock_input.return_value = "n"
        cmd_skill_remove("keep-me")
        assert len(load_skills()) == 1
        assert "Cancelado" in capsys.readouterr().out

    def test_remove_not_found(self, nexus_env, capsys):
        from nexus._legacy_main import cmd_skill_remove
        cmd_skill_remove("nonexistent")
        assert "não encontrado" in capsys.readouterr().out

    def test_remove_ctrl_c(self, nexus_env, mock_input, capsys):
        from nexus._legacy_main import cmd_skill_remove
        entry = SkillEntry(title="Ctrl C Skill", slug="ctrl-c-skill", scope="global")
        save_skill_entry(entry)
        mock_input.side_effect = KeyboardInterrupt
        cmd_skill_remove("ctrl-c-skill")
        # skill should still be there
        assert len(load_skills()) == 1
        assert "Cancelado" in capsys.readouterr().out


class TestCmdSkillGaps:
    def test_no_data_json(self, nexus_env, capsys):
        from nexus._legacy_main import cmd_skill_gaps
        # data.json does not exist by default in nexus_env
        cmd_skill_gaps()
        out = capsys.readouterr().out
        assert "data.json" in out

    def test_all_up_to_date(self, nexus_env, capsys):
        from nexus._legacy_main import cmd_skill_gaps
        data_json = nexus_env / "data.json"
        payload = {
            "skills": {
                "my-skill": {
                    "title": "my-skill", "url": None,
                    "presence": {
                        "host-a": {"global": True},
                        "host-b": {"global": True},
                    },
                }
            },
            "environments": [
                {"hostname": "host-a", "name": "host-a", "location": "a", "last_seen": ""},
                {"hostname": "host-b", "name": "host-b", "location": "b", "last_seen": ""},
            ],
        }
        data_json.write_text(json.dumps(payload), encoding="utf-8")
        cmd_skill_gaps()
        out = capsys.readouterr().out
        assert "atualizados" in out

    def test_gaps_detected(self, nexus_env, capsys):
        from nexus._legacy_main import cmd_skill_gaps
        data_json = nexus_env / "data.json"
        payload = {
            "skills": {
                "my-skill": {
                    "title": "my-skill", "url": None,
                    "presence": {
                        "host-a": {"global": True},
                    },
                }
            },
            "environments": [
                {"hostname": "host-a", "name": "host-a", "location": "a", "last_seen": ""},
                {"hostname": "host-b", "name": "host-b", "location": "b", "last_seen": ""},
            ],
        }
        data_json.write_text(json.dumps(payload), encoding="utf-8")
        cmd_skill_gaps()
        out = capsys.readouterr().out
        assert "host-b" in out
        assert "my-skill" in out

    def test_no_skills_in_data_json(self, nexus_env, capsys):
        from nexus._legacy_main import cmd_skill_gaps
        data_json = nexus_env / "data.json"
        data_json.write_text(json.dumps({"skills": {}, "environments": []}), encoding="utf-8")
        cmd_skill_gaps()
        out = capsys.readouterr().out
        assert "Nenhum skill" in out


class TestCmdSkillDispatcher:
    def test_list_subcmd(self, nexus_env, capsys):
        from nexus._legacy_main import cmd_skill
        import argparse
        result = cmd_skill(argparse.Namespace(skill_cmd="list"))
        assert result == 0

    def test_unknown_subcmd(self, nexus_env, capsys):
        from nexus._legacy_main import cmd_skill
        import argparse
        result = cmd_skill(argparse.Namespace(skill_cmd="unknown"))
        assert result == 1
        assert "desconhecido" in capsys.readouterr().out

    def test_edit_no_query(self, nexus_env, capsys):
        from nexus._legacy_main import cmd_skill
        import argparse
        result = cmd_skill(argparse.Namespace(skill_cmd="edit", query=None))
        assert result == 1

    def test_remove_no_query(self, nexus_env, capsys):
        from nexus._legacy_main import cmd_skill
        import argparse
        result = cmd_skill(argparse.Namespace(skill_cmd="remove", query=None))
        assert result == 1
