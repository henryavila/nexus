"""Tests for untested library functions across multiple modules."""

import pytest
from unittest.mock import patch


class TestRemoveProject:
    def test_remove_by_name(self, nexus_env):
        from nexus.registry import add_project, remove_project, load_registry, ProjectEntry

        add_project(ProjectEntry(name="ToRemove", domain="pessoal"))
        assert len(load_registry()) == 1
        result = remove_project("ToRemove")
        assert result is True
        assert len(load_registry()) == 0

    def test_remove_by_path(self, nexus_env, tmp_path):
        from nexus.registry import add_project, remove_project, load_registry, ProjectEntry

        proj_dir = tmp_path / "myproject"
        proj_dir.mkdir()
        add_project(ProjectEntry(name="MyProject", path=str(proj_dir), domain="pessoal"))
        assert len(load_registry()) == 1

        result = remove_project(str(proj_dir))
        assert result is True
        assert len(load_registry()) == 0

    def test_remove_not_found(self, nexus_env):
        from nexus.registry import remove_project

        result = remove_project("ghost")
        assert result is False

    def test_remove_leaves_others_intact(self, nexus_env):
        from nexus.registry import add_project, remove_project, load_registry, ProjectEntry

        add_project(ProjectEntry(name="Alpha", domain="pessoal"))
        add_project(ProjectEntry(name="Beta", domain="pessoal"))
        assert len(load_registry()) == 2

        result = remove_project("Alpha")
        assert result is True
        remaining = load_registry()
        assert len(remaining) == 1
        assert remaining[0].name == "Beta"

    def test_remove_by_slug(self, nexus_env):
        from nexus.registry import add_project, remove_project, load_registry, ProjectEntry

        _, entry = add_project(ProjectEntry(name="SlugProject", domain="pessoal"))
        slug = entry.slug
        assert slug

        result = remove_project(slug)
        assert result is True
        assert len(load_registry()) == 0


class TestBackfillSlugs:
    def test_backfills_missing_slugs(self, nexus_env):
        from nexus.registry import add_project, save_registry, load_registry, backfill_slugs, ProjectEntry

        # Add a project normally (it will get a slug)
        add_project(ProjectEntry(name="WithSlug", domain="pessoal"))

        # Manually save a project without a slug by manipulating the registry
        entries = load_registry()
        entries.append(ProjectEntry(name="NoSlug", domain="pessoal", slug=""))
        save_registry(entries)

        # Verify we have two entries, one without slug
        entries = load_registry()
        assert len(entries) == 2
        no_slug_entries = [e for e in entries if not e.slug]
        assert len(no_slug_entries) == 1

        count = backfill_slugs()
        assert count == 1

        # All entries should now have slugs
        entries = load_registry()
        for e in entries:
            assert e.slug, f"Expected slug for entry '{e.name}', got empty"

    def test_no_backfill_needed(self, nexus_env):
        from nexus.registry import add_project, backfill_slugs, ProjectEntry

        add_project(ProjectEntry(name="AlreadyHasSlug", domain="pessoal"))

        count = backfill_slugs()
        assert count == 0

    def test_backfill_empty_registry(self, nexus_env):
        from nexus.registry import backfill_slugs

        count = backfill_slugs()
        assert count == 0

    def test_backfill_generates_unique_slugs(self, nexus_env):
        from nexus.registry import save_registry, load_registry, backfill_slugs, ProjectEntry

        # Save two projects with no slugs but names that would produce the same slug
        save_registry([
            ProjectEntry(name="My Project", domain="pessoal", slug=""),
            ProjectEntry(name="My Project", domain="trabalho", slug=""),
        ])

        count = backfill_slugs()
        assert count == 2

        entries = load_registry()
        slugs = [e.slug for e in entries]
        # All slugs must be set and unique
        assert all(slugs)
        assert len(set(slugs)) == len(slugs)


class TestRemoveSkill:
    def test_remove_skill_direct(self, nexus_env):
        from nexus.skills import SkillEntry, save_skill_entry, load_skills, remove_skill

        save_skill_entry(SkillEntry(title="Bye", slug="bye", scope="global"))
        assert len(load_skills()) == 1

        result = remove_skill("bye")
        assert result is True
        assert len(load_skills()) == 0

    def test_remove_skill_not_found(self, nexus_env):
        from nexus.skills import remove_skill

        result = remove_skill("nonexistent")
        assert result is False

    def test_remove_skill_leaves_others(self, nexus_env):
        from nexus.skills import SkillEntry, save_skill_entry, load_skills, remove_skill

        save_skill_entry(SkillEntry(title="Keep", slug="keep", scope="global"))
        save_skill_entry(SkillEntry(title="Delete", slug="delete", scope="global"))
        assert len(load_skills()) == 2

        result = remove_skill("delete")
        assert result is True
        remaining = load_skills()
        assert len(remaining) == 1
        assert remaining[0].slug == "keep"


class TestGetEnvironmentPath:
    def test_returns_path(self, nexus_env):
        from nexus.environment import save_environments, EnvironmentEntry, get_environment_path

        save_environments([EnvironmentEntry(
            hostname="mypc",
            name="My PC",
            location="casa",
            paths={"my-proj": "/home/user/my-proj"},
        )])
        result = get_environment_path("my-proj", "mypc")
        assert result == "/home/user/my-proj"

    def test_returns_none_missing_slug(self, nexus_env):
        from nexus.environment import save_environments, EnvironmentEntry, get_environment_path

        save_environments([EnvironmentEntry(
            hostname="mypc",
            name="My PC",
            location="casa",
            paths={"my-proj": "/home/user/my-proj"},
        )])
        result = get_environment_path("other-proj", "mypc")
        assert result is None

    def test_returns_none_missing_host(self, nexus_env):
        from nexus.environment import get_environment_path

        result = get_environment_path("ghost", "nohost")
        assert result is None

    def test_returns_none_empty_environments(self, nexus_env):
        from nexus.environment import get_environment_path

        result = get_environment_path("any-proj", "any-host")
        assert result is None

    def test_multiple_environments(self, nexus_env):
        from nexus.environment import save_environments, EnvironmentEntry, get_environment_path

        save_environments([
            EnvironmentEntry(
                hostname="laptop",
                name="Laptop",
                location="home",
                paths={"proj-a": "/home/laptop/proj-a"},
            ),
            EnvironmentEntry(
                hostname="desktop",
                name="Desktop",
                location="office",
                paths={"proj-a": "/home/desktop/proj-a"},
            ),
        ])
        assert get_environment_path("proj-a", "laptop") == "/home/laptop/proj-a"
        assert get_environment_path("proj-a", "desktop") == "/home/desktop/proj-a"


class TestPickEditor:
    def test_pick_single_editor_returns_it(self, nexus_env):
        """When only one editor is configured, pick_editor returns it without prompting."""
        from nexus.editors import EditorConfig, pick_editor, save_editors

        editor = EditorConfig(name="vim", command="vim", type="terminal")
        save_editors([editor], "vim")

        result = pick_editor()
        assert result is not None
        assert result.name == "vim"

    def test_pick_no_editors_calls_add(self, nexus_env):
        """When no editors configured, pick_editor falls through to add_editor."""
        from nexus.editors import pick_editor

        # Patch add_editor to avoid interactive prompt
        with patch("nexus.editors.add_editor", return_value=None) as mock_add:
            result = pick_editor()
            mock_add.assert_called_once()
            assert result is None

    def test_pick_multiple_editors_with_input(self, nexus_env, mock_input):
        """When multiple editors configured, pick_editor prompts and returns selected."""
        from nexus.editors import EditorConfig, pick_editor, save_editors

        editors = [
            EditorConfig(name="vim", command="vim", type="terminal"),
            EditorConfig(name="nano", command="nano", type="terminal"),
        ]
        save_editors(editors, "vim")

        # Simulate the user choosing "2" (nano)
        mock_input.return_value = "2"

        result = pick_editor()
        assert result is not None
        assert result.name == "nano"

    def test_pick_multiple_editors_default_on_empty_input(self, nexus_env, mock_input):
        """Empty input selects the default editor."""
        from nexus.editors import EditorConfig, pick_editor, save_editors

        editors = [
            EditorConfig(name="vim", command="vim", type="terminal"),
            EditorConfig(name="nano", command="nano", type="terminal"),
        ]
        save_editors(editors, "nano")

        # Empty input → uses default_idx (nano is default, so index 2)
        mock_input.return_value = ""

        result = pick_editor()
        assert result is not None
        assert result.name == "nano"

    def test_pick_multiple_editors_cancelled(self, nexus_env, mock_input):
        """KeyboardInterrupt during input returns None."""
        from nexus.editors import EditorConfig, pick_editor, save_editors

        editors = [
            EditorConfig(name="vim", command="vim", type="terminal"),
            EditorConfig(name="nano", command="nano", type="terminal"),
        ]
        save_editors(editors, "vim")

        mock_input.side_effect = KeyboardInterrupt

        result = pick_editor()
        assert result is None
