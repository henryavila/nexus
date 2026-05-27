"""Tests for evolution commands: replace, absorb, split."""
import json
import pytest
from unittest.mock import patch
from nexus.registry import ProjectEntry, add_project, load_registry
from nexus.apps import load_apps


class TestProjectReplace:
    def _add_project(self, name="Old Project", slug="old-proj", **kwargs):
        entry = ProjectEntry(name=name, slug=slug, domain="pessoal", nature="contexto", **kwargs)
        add_project(entry)
        return slug

    def test_replace_with_existing_project(self, nexus_env, mock_input, capsys, tmp_path):
        from nexus._legacy_main import cmd_project_replace
        import argparse

        self._add_project(name="Old", slug="old")
        self._add_project(name="New", slug="new")
        mock_input.return_value = "s"

        result = cmd_project_replace(argparse.Namespace(old="old", new="new"))

        assert result == 0
        entries = load_registry()
        old = next(e for e in entries if e.slug == "old")
        new = next(e for e in entries if e.slug == "new")
        assert old.status == "replaced"
        assert "Substituído por new" in old.note
        assert "Origem: old" in new.note

    def test_replace_cancelled(self, nexus_env, mock_input, capsys):
        from nexus._legacy_main import cmd_project_replace
        import argparse

        self._add_project(name="Old", slug="old")
        self._add_project(name="New", slug="new")
        mock_input.return_value = "n"

        result = cmd_project_replace(argparse.Namespace(old="old", new="new"))

        assert result == 0
        out = capsys.readouterr().out
        assert "Cancelado" in out

    def test_replace_not_found(self, nexus_env, capsys):
        from nexus._legacy_main import cmd_project_replace
        import argparse

        result = cmd_project_replace(argparse.Namespace(old="ghost", new="other"))

        assert result == 1
        out = capsys.readouterr().out
        assert "não encontrado" in out


class TestProjectAbsorb:
    def _add_project(self, name="Project", slug="proj", **kwargs):
        entry = ProjectEntry(name=name, slug=slug, domain="pessoal", nature="contexto", **kwargs)
        add_project(entry)
        return slug

    def test_absorb_removes_minor(self, nexus_env, mock_input, capsys):
        from nexus._legacy_main import cmd_project_absorb
        import argparse

        self._add_project(name="Minor", slug="minor")
        self._add_project(name="Major", slug="major")
        mock_input.return_value = "s"

        result = cmd_project_absorb(argparse.Namespace(minor="minor", major="major"))

        assert result == 0
        entries = load_registry()
        slugs = [e.slug for e in entries]
        assert "minor" not in slugs
        major = next(e for e in entries if e.slug == "major")
        assert "Absorveu: minor" in major.note

    def test_absorb_cancelled(self, nexus_env, mock_input, capsys):
        from nexus._legacy_main import cmd_project_absorb
        import argparse

        self._add_project(name="Minor", slug="minor")
        self._add_project(name="Major", slug="major")
        mock_input.return_value = "n"

        result = cmd_project_absorb(argparse.Namespace(minor="minor", major="major"))

        assert result == 0
        assert len(load_registry()) == 2


class TestProjectSplit:
    def _add_project(self, name="Project", slug="proj", **kwargs):
        entry = ProjectEntry(name=name, slug=slug, domain="tech", nature="ferramenta", **kwargs)
        add_project(entry)
        return slug

    def test_split_creates_new_projects(self, nexus_env, mock_input, capsys, tmp_path):
        from nexus._legacy_main import cmd_project_split
        import argparse

        self._add_project(name="Original", slug="orig")
        p1 = tmp_path / "new1"
        p2 = tmp_path / "new2"
        p1.mkdir()
        p2.mkdir()
        mock_input.return_value = "s"

        result = cmd_project_split(argparse.Namespace(
            old="orig",
            paths=[str(p1), str(p2)],
        ))

        assert result == 0
        entries = load_registry()
        orig = next(e for e in entries if e.slug == "orig")
        assert orig.status == "replaced"
        assert "Dividido em" in orig.note
        # Should have 3 entries: orig + 2 new
        assert len(entries) == 3

    def test_split_cancelled(self, nexus_env, mock_input, tmp_path):
        from nexus._legacy_main import cmd_project_split
        import argparse

        self._add_project(name="Original", slug="orig")
        p1 = tmp_path / "new1"
        p1.mkdir()
        mock_input.return_value = "n"

        result = cmd_project_split(argparse.Namespace(old="orig", paths=[str(p1)]))

        assert result == 0
        assert len(load_registry()) == 1


class TestIdeaPromoteToApp:
    def test_promote_idea_to_app(self, nexus_env, mock_input, capsys):
        from nexus.ideas import IdeaEntry, add_idea, load_ideas
        from nexus._legacy_main import cmd_idea_promote
        import argparse

        idea = IdeaEntry(title="My Idea", description="Desc", domain="trabalho", priority="high")
        result = add_idea(idea)
        mock_input.return_value = "s"

        cmd_idea_promote(argparse.Namespace(
            query=result.id, app=True,
            name=None, domain=None, github=None, url=None,
        ))

        apps = load_apps()
        assert len(apps) == 1
        assert apps[0].name == "My Idea"
        assert apps[0].domain == "trabalho"
        # Idea should be removed
        ideas = load_ideas()
        assert len(ideas) == 0

    def test_promote_idea_to_app_cancelled(self, nexus_env, mock_input, capsys):
        from nexus.ideas import IdeaEntry, add_idea, load_ideas
        from nexus._legacy_main import cmd_idea_promote
        import argparse

        idea = IdeaEntry(title="My Idea", domain="trabalho")
        result = add_idea(idea)
        mock_input.return_value = "n"

        cmd_idea_promote(argparse.Namespace(
            query=result.id, app=True,
            name=None, domain=None, github=None, url=None,
        ))

        assert len(load_apps()) == 0
        assert len(load_ideas()) == 1

    def test_promote_idea_to_app_atomicity(self, nexus_env, mock_input, capsys):
        """Idea must NOT be removed if add_app raises."""
        from nexus.ideas import IdeaEntry, add_idea, load_ideas
        from nexus._legacy_main import cmd_idea_promote
        import argparse

        idea = IdeaEntry(title="Atomic Idea", description="Desc", domain="trabalho", priority="high")
        result = add_idea(idea)
        mock_input.return_value = "s"

        with patch("nexus.apps.add_app", side_effect=RuntimeError("db error")):
            cmd_idea_promote(argparse.Namespace(
                query=result.id, app=True,
                name=None, domain=None, github=None, url=None,
            ))

        # Idea must survive because add_app failed
        ideas = load_ideas()
        assert len(ideas) == 1
        assert ideas[0].id == result.id
        assert "Erro" in capsys.readouterr().out
