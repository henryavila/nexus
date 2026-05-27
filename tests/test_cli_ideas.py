import json
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from nexus.ideas import IdeaEntry, add_idea, load_ideas, _update_ideas_in_data_json


class TestIdeaCommands(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.tmpdir.name)
        self.ideas_yml = self.data_dir / "ideas.yml"
        self.data_json = self.data_dir / "data.json"
        self.lock_file = self.data_dir / ".nexus.lock"
        self.projects_yml = self.data_dir / "projects.yml"

        self.patches = [
            patch("nexus.ideas.IDEAS_YML", self.ideas_yml),
            patch("nexus.ideas.DATA_JSON", self.data_json),
            patch("nexus.ideas.LOCK_FILE", self.lock_file),
            patch("nexus.registry.PROJECTS_YML", self.projects_yml),
            patch("nexus.registry.DATA_JSON", self.data_json),
            patch("nexus.registry.DATA_DIR", self.data_dir),
            patch("nexus.scanner.DATA_JSON", self.data_json),
            patch("nexus.scanner.LOCK_FILE", self.lock_file),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.tmpdir.cleanup()

    @patch("builtins.input")
    def test_cmd_idea_add(self, mock_input):
        from nexus._legacy_main import cmd_idea_add
        import argparse
        mock_input.side_effect = [
            "Bot de reunioes",    # title
            "Resume com IA",     # description
            "7",                  # domain = trabalho (sorted DEFAULT_DOMAINS)
            "1",                  # priority = high
            "ia, audio",         # tags
            "",                   # references
            "Usar Whisper",       # notes
        ]
        result = cmd_idea_add(argparse.Namespace())
        self.assertEqual(result, 0)
        ideas = load_ideas()
        self.assertEqual(len(ideas), 1)
        self.assertEqual(ideas[0].title, "Bot de reunioes")
        self.assertEqual(ideas[0].domain, "trabalho")

    @patch("builtins.input")
    def test_cmd_idea_edit(self, mock_input):
        from nexus._legacy_main import cmd_idea_edit
        import argparse
        idea = add_idea(IdeaEntry(title="Original", domain="pessoal"))
        mock_input.side_effect = [
            "Updated",           # title
            "",                   # description (keep)
            "1",                  # domain (keep current)
            "1",                  # priority (keep current)
            "",                   # tags (keep)
            "",                   # references (keep)
            "",                   # notes (keep)
        ]
        result = cmd_idea_edit(argparse.Namespace(query=idea.id))
        self.assertEqual(result, 0)
        ideas = load_ideas()
        self.assertEqual(ideas[0].title, "Updated")

    @patch("builtins.input")
    def test_cmd_idea_remove(self, mock_input):
        from nexus._legacy_main import cmd_idea_remove
        import argparse
        idea = add_idea(IdeaEntry(title="To Remove"))
        mock_input.return_value = "s"  # confirm
        result = cmd_idea_remove(argparse.Namespace(query=idea.id))
        self.assertEqual(result, 0)
        ideas = load_ideas()
        self.assertEqual(len(ideas), 0)

    @patch("builtins.input")
    def test_cmd_idea_promote(self, mock_input):
        from nexus._legacy_main import cmd_idea_promote
        import argparse
        idea = add_idea(IdeaEntry(
            title="Bot de reunioes",
            description="Resume com IA",
            domain="trabalho",
            notes="Usar Whisper",
        ))
        project_dir = Path(self.tmpdir.name) / "bot-project"
        project_dir.mkdir()
        mock_input.side_effect = [
            "S",                        # confirm promote
            str(project_dir),           # path
            "",                         # name (keep)
            "",                         # description (keep)
            "1",                        # domain (keep mapped)
            "1",                        # nature
            "",                         # icon
            "",                         # url
            "",                         # repo
        ]
        with patch("nexus._legacy_main.ensure_project_config", return_value=(False, False)):
            with patch("nexus._legacy_main.install_git_hook", return_value=False):
                with patch("nexus._legacy_main.install_claude_hook", return_value=False):
                    result = cmd_idea_promote(argparse.Namespace(query=idea.id, app=False, name=None, domain=None, github=None, url=None))
        self.assertEqual(result, 0)
        # Idea should be removed
        ideas = load_ideas()
        self.assertEqual(len(ideas), 0)

    @patch("builtins.input")
    def test_promote_path_with_quotes(self, mock_input):
        """Path com aspas deve ser aceito (usuário cola path entre aspas)."""
        from nexus._legacy_main import cmd_idea_promote
        import argparse
        idea = add_idea(IdeaEntry(
            title="Quoted Path",
            description="Test",
            domain="pessoal",
        ))
        project_dir = Path(self.tmpdir.name) / "quoted-project"
        project_dir.mkdir()
        # Simula path digitado com aspas duplas
        mock_input.side_effect = [
            "S",                                # confirm
            f'"{project_dir}"',                 # path com aspas
            "",                                 # name
            "",                                 # description
            "1",                                # domain
            "1",                                # nature
            "",                                 # icon
            "",                                 # url
            "",                                 # repo
        ]
        with patch("nexus._legacy_main.ensure_project_config", return_value=(False, False)):
            with patch("nexus._legacy_main.install_git_hook", return_value=False):
                with patch("nexus._legacy_main.install_claude_hook", return_value=False):
                    result = cmd_idea_promote(argparse.Namespace(query=idea.id, app=False, name=None, domain=None, github=None, url=None))
        self.assertEqual(result, 0)
        ideas = load_ideas()
        self.assertEqual(len(ideas), 0)

    def test_ideas_in_data_json_via_update(self):
        add_idea(IdeaEntry(title="Idea A", priority="high"))
        add_idea(IdeaEntry(title="Idea B", priority="low"))
        _update_ideas_in_data_json()
        data = json.loads(self.data_json.read_text())
        self.assertIn("ideas", data)
        self.assertEqual(len(data["ideas"]), 2)
        # Sorted: high first
        self.assertEqual(data["ideas"][0]["priority"], "high")

    @patch("nexus.scanner.scan_project")
    def test_scan_one_preserves_ideas(self, mock_scan):
        from nexus.scanner import scan_one
        from nexus.registry import add_project
        from nexus.registry import ProjectEntry as PE

        # Register a project
        project_dir = Path(self.tmpdir.name) / "myproj"
        project_dir.mkdir()
        add_project(PE(path=str(project_dir), name="myproj"))

        # Write data.json with ideas already present
        data = {
            "version": "3.0",
            "last_full_scan": None,
            "projects": [],
            "ideas": [{"id": "abc123", "title": "Preserved Idea"}],
        }
        self.data_json.write_text(json.dumps(data))

        # Mock scan_project to return a valid result
        mock_scan.return_value = {
            "class": "git",
            "last_activity": "2026-03-06",
            "git": {"branch": "main", "last_commit_date": "2026-03-06",
                     "last_commit_message": "test", "dirty": False, "repo": None},
            "filesystem": None,
            "health": {"path_exists": True, "claude_memory_portable": None, "web_compliant": None},
            "last_scanned": "2026-03-06T12:00:00",
        }

        # Run scan_one — this should update the project but preserve ideas
        result = scan_one(str(project_dir))
        self.assertIsNotNone(result)

        # Verify ideas key is preserved in data.json
        loaded = json.loads(self.data_json.read_text())
        self.assertIn("ideas", loaded)
        self.assertEqual(len(loaded["ideas"]), 1)
        self.assertEqual(loaded["ideas"][0]["title"], "Preserved Idea")

    @patch("builtins.input")
    def test_promote_preserves_context(self, mock_input):
        from nexus._legacy_main import cmd_idea_promote
        from nexus.registry import load_registry
        import argparse

        idea = add_idea(IdeaEntry(
            title="Context Test",
            description="Desc",
            domain="pessoal",
            notes="Important notes",
            references=["https://ref.com"],
        ))
        project_dir = Path(self.tmpdir.name) / "ctx-project"
        project_dir.mkdir()
        mock_input.side_effect = [
            "S",                        # confirm
            str(project_dir),           # path
            "",                         # name (keep)
            "",                         # description (keep)
            "1",                        # domain (keep mapped)
            "1",                        # nature
            "",                         # icon
            "",                         # url
            "",                         # repo
        ]
        with patch("nexus._legacy_main.ensure_project_config", return_value=(False, False)):
            with patch("nexus._legacy_main.install_git_hook", return_value=False):
                with patch("nexus._legacy_main.install_claude_hook", return_value=False):
                    cmd_idea_promote(argparse.Namespace(query=idea.id, app=False, name=None, domain=None, github=None, url=None))

        # Verify the project was created with context in note field
        projects = load_registry()
        self.assertEqual(len(projects), 1)
        note = projects[0].note
        self.assertIn("Refs: https://ref.com", note)
        self.assertIn("Notas: Important notes", note)

    @patch("builtins.input")
    def test_promote_preserves_domain(self, mock_input):
        from nexus._legacy_main import cmd_idea_promote
        from nexus.registry import load_registry
        import argparse

        idea = add_idea(IdeaEntry(title="Cat Keep", domain="trabalho"))
        project_dir = Path(self.tmpdir.name) / "cat-project"
        project_dir.mkdir()
        mock_input.side_effect = [
            "S",                        # confirm
            str(project_dir),           # path
            "",                         # name (keep)
            "",                         # description (keep)
            "1",                        # domain (keep = trabalho)
            "1",                        # nature
            "",                         # icon
            "",                         # url
            "",                         # repo
        ]
        with patch("nexus._legacy_main.ensure_project_config", return_value=(False, False)):
            with patch("nexus._legacy_main.install_git_hook", return_value=False):
                with patch("nexus._legacy_main.install_claude_hook", return_value=False):
                    cmd_idea_promote(argparse.Namespace(query=idea.id, app=False, name=None, domain=None, github=None, url=None))

        projects = load_registry()
        self.assertEqual(len(projects), 1)
        self.assertEqual(projects[0].domain, "trabalho")

    def test_promote_with_none_fields(self):
        idea = IdeaEntry(
            title="Clean Promote",
            notes=None,
            references=None,
        )
        note_parts = []
        if idea.references:
            note_parts.append(f"Refs: {', '.join(idea.references)}")
        if idea.notes:
            note_parts.append(f"Notas: {idea.notes}")
        project_note = " | ".join(note_parts) if note_parts else None
        # Should be None (no "None" strings)
        self.assertIsNone(project_note)

    def test_bare_nexus_idea_shows_help(self):
        from nexus._legacy_main import cmd_idea
        import argparse
        args = argparse.Namespace()
        args.idea_command = None
        result = cmd_idea(args)
        self.assertEqual(result, 1)

    def test_data_json_version_bumped(self):
        add_idea(IdeaEntry(title="Version Test"))
        _update_ideas_in_data_json()
        data = json.loads(self.data_json.read_text())
        self.assertEqual(data["version"], "3.0")


if __name__ == "__main__":
    unittest.main()
