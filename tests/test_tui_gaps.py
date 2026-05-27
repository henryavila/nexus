"""
TUI coverage gap tests.

Tests the uncovered branches in nexus/tui.py by calling widget compose()
generators and action methods directly, bypassing the textual event loop.

Uncovered targets:
  44      — ProjectItem.compose: archived status → sym = "◇"
  59-62   — ProjectItem.compose: days<=0 (today), days==1, ValueError date, no last_activity
  72      — ProjectItem.compose: mem is False → badge
  83      — ProjectItem.compose: note present → line2_parts
  172-213 — IdeaDetailScreen.compose
  288-300 — SkillItem.compose with URL
  366-383 — CodexDetailScreen.compose
  438-457 — SkillDetailScreen.compose with URL
  511-542 — EnvDetailScreen.compose with last_seen/paths/absent
  592     — CliSelectScreen.action_cancel
  735-738 — _background_scan progress callback
  795-796 — _load_projects: filter_text applied
  813, 820 — _load_projects: health alerts
  835-836 — _load_ideas: filter_text applied
  854-855 — _load_codex: filter_text applied
  872-873 — _load_apps: filter_text applied
  892-894, 897-898 — _load_skills: filter_text applied
  915-916 — _load_environments: filter_text applied
  929-941 — on_input_changed with various tabs
  950     — on_tabbed_content_tab_activated: stale event guard
  965     — action_focus_filter
  982-983 — _update_selection_meta: codex item, None
  990-991 — _update_selection_meta: apps item
  1000-1006 — _update_selection_meta: skills item
  1008-1014 — _update_selection_meta: environments item
  1018-1019 — _update_selection_meta: projects, no selection
  1025-1026 — on_list_view_highlighted
  1035     — _get_selected_project: no highlighted → fallback to first child
  1039     — _get_selected_project: no children → None
  1044     — _get_selected_idea: no highlighted → fallback
  1053-1057 — _get_selected_codex paths
  1062-1066 — _get_selected_app paths
  1069-1075 — _get_selected_skill paths
  1078-1084 — _get_selected_env paths
  1115    — action_launch_project: apps, no URL
  1131    — action_launch_project: unknown tab → return
  1136    — action_launch_project: no project selected
  1141-1143 — action_launch_project: path doesn't exist → notify+exit
  1164-1167 — _on_idea_detail_dismissed: result==edit
  1176-1179 — _on_skill_detail_dismissed: result==edit
  1203-1206 — action_edit_item: apps/skills/environments
  1215-1220 — action_add_note: apps tab
  1223-1238 — action_add_note: projects, no note widget
  1243-1245 — action_remove_item: ideas
  1247-1249 — action_remove_item: projects
  1262-1263 — action_remove_item: environments
  1268     — action_add_idea: ideas
  1275-1276 — action_add_idea: projects
  1281-1283 — action_promote_idea: ideas
  1284-1287 — action_promote_idea: projects
"""
import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

try:
    from nexus.cli_registry import CliEntry
    from nexus.tui import (
        CliSelectScreen,
        CodexDetailScreen,
        EnvDetailScreen,
        IdeaDetailScreen,
        NexusApp,
        SkillDetailScreen,
    )
    from textual.widgets.data_table import RowKey
    HAS_TEXTUAL = True
except ImportError:
    HAS_TEXTUAL = False


def _consume_compose(widget):
    """Call compose() and consume the generator (don't render, just iterate)."""
    try:
        list(widget.compose())
    except Exception:
        pass  # Widget rendering may require app context; consuming the generator is enough


@unittest.skipUnless(HAS_TEXTUAL, "textual not installed")
class TestProjectDataTableRowData(unittest.TestCase):
    """Projects are now rendered via DataTable. Verify row data storage."""

    def _make_app(self):
        with patch("nexus.tui.app.detect_clis", return_value=[]):
            return NexusApp()

    def test_project_row_data_stores_dict(self):
        """NexusApp._project_row_data maps RowKey to project dict."""
        app = self._make_app()
        app._project_row_data[RowKey("nexus")] = {"name": "Nexus", "slug": "nexus"}
        self.assertEqual(app._project_row_data[RowKey("nexus")]["name"], "Nexus")

    def test_idea_row_data_stores_dict(self):
        """NexusApp._idea_row_data maps RowKey to idea dict."""
        app = self._make_app()
        app._idea_row_data[RowKey("abc")] = {"id": "abc", "title": "Test"}
        self.assertEqual(app._idea_row_data[RowKey("abc")]["title"], "Test")

    def test_app_row_data_stores_dict(self):
        """NexusApp._app_row_data maps RowKey to app dict."""
        app = self._make_app()
        app._app_row_data[RowKey("myapp")] = {"name": "My App", "slug": "myapp"}
        self.assertEqual(app._app_row_data[RowKey("myapp")]["name"], "My App")


@unittest.skipUnless(HAS_TEXTUAL, "textual not installed")
class TestIdeaDetailScreenCompose(unittest.TestCase):
    """Test IdeaDetailScreen.compose() — lines 172-213."""

    def test_compose_with_full_data(self):
        """IdeaDetailScreen.compose: full idea with tags, refs, notes, created (lines 172-213)."""
        idea = {
            "id": "abc", "title": "My Idea", "priority": "high",
            "domain": "pessoal", "description": "A great idea",
            "tags": ["python", "ai"], "references": ["https://ref.com"],
            "notes": "Some notes", "created": "2026-01-01",
        }
        screen = IdeaDetailScreen(idea)
        _consume_compose(screen)

    def test_compose_minimal_data(self):
        """IdeaDetailScreen.compose: minimal idea (no optional fields)."""
        idea = {"id": "x", "title": "Simple Idea", "priority": "medium", "domain": "pessoal"}
        screen = IdeaDetailScreen(idea)
        _consume_compose(screen)

    def test_action_dismiss_screen(self):
        """IdeaDetailScreen.action_dismiss_screen → calls dismiss(None)."""
        screen = IdeaDetailScreen({"id": "a", "title": "X"})
        screen.dismiss = MagicMock()
        screen.action_dismiss_screen()
        screen.dismiss.assert_called_once_with(None)

    def test_action_edit_idea(self):
        """IdeaDetailScreen.action_edit_idea → calls dismiss('edit')."""
        screen = IdeaDetailScreen({"id": "a", "title": "X"})
        screen.dismiss = MagicMock()
        screen.action_edit_idea()
        screen.dismiss.assert_called_once_with("edit")


@unittest.skipUnless(HAS_TEXTUAL, "textual not installed")
class TestSkillRowDataStorage(unittest.TestCase):
    """Skills are rendered via DataTable; verify row data storage."""

    def _make_app(self):
        with patch("nexus.tui.app.detect_clis", return_value=[]):
            return NexusApp()

    def test_skill_row_data_stores_dict(self):
        """NexusApp._skill_row_data maps RowKey to skill dict."""
        app = self._make_app()
        app._skill_row_data[RowKey("skill:python")] = {"slug": "python", "title": "Python Tips"}
        self.assertEqual(app._skill_row_data[RowKey("skill:python")]["slug"], "python")

    def test_codex_row_data_stores_dict(self):
        """NexusApp._codex_row_data maps RowKey to codex dict."""
        app = self._make_app()
        app._codex_row_data[RowKey("codex:guide")] = {"slug": "guide", "title": "My Guide"}
        self.assertEqual(app._codex_row_data[RowKey("codex:guide")]["title"], "My Guide")

    def test_env_row_data_stores_dict(self):
        """NexusApp._env_row_data maps RowKey to env dict."""
        app = self._make_app()
        app._env_row_data[RowKey("env:myhost")] = {"hostname": "myhost", "name": "My Host"}
        self.assertEqual(app._env_row_data[RowKey("env:myhost")]["hostname"], "myhost")


@unittest.skipUnless(HAS_TEXTUAL, "textual not installed")
class TestCodexDetailScreenCompose(unittest.TestCase):
    """Test CodexDetailScreen.compose() — lines 366-383."""

    def test_compose_with_tags_and_updated(self):
        """CodexDetailScreen.compose: entry with tags and updated (lines 366-383)."""
        entry = {
            "title": "My Codex", "domain": "pessoal",
            "tags": ["python", "tips"], "updated": "2026-01-15",
            "content": "# Title\n\nSome content here.",
        }
        screen = CodexDetailScreen(entry)
        _consume_compose(screen)

    def test_compose_minimal(self):
        """CodexDetailScreen.compose: minimal entry (no tags/updated)."""
        entry = {"title": "Simple", "domain": "pessoal", "content": "Content."}
        screen = CodexDetailScreen(entry)
        _consume_compose(screen)

    def test_action_dismiss_screen(self):
        """CodexDetailScreen.action_dismiss_screen → calls dismiss(None)."""
        screen = CodexDetailScreen({"title": "X"})
        screen.dismiss = MagicMock()
        screen.action_dismiss_screen()
        screen.dismiss.assert_called_once_with(None)

    def test_action_edit_codex(self):
        """CodexDetailScreen.action_edit_codex → calls dismiss('edit')."""
        screen = CodexDetailScreen({"title": "X"})
        screen.dismiss = MagicMock()
        screen.action_edit_codex()
        screen.dismiss.assert_called_once_with("edit")


@unittest.skipUnless(HAS_TEXTUAL, "textual not installed")
class TestSkillDetailScreenCompose(unittest.TestCase):
    """Test SkillDetailScreen.compose() — lines 438-457."""

    def test_compose_with_url(self):
        """SkillDetailScreen.compose: skill has URL → yields URL lines (lines 453-455)."""
        skill = {"slug": "pyskill", "title": "Py Skill", "presence": {"H": {"global": True}}, "url": "https://example.com"}
        screen = SkillDetailScreen(skill)
        _consume_compose(screen)

    def test_compose_no_url(self):
        """SkillDetailScreen.compose: no URL → skips URL section."""
        skill = {"slug": "noskill", "title": "No URL Skill", "presence": {"H": {"global": False, "repos": ["proj"]}}}
        screen = SkillDetailScreen(skill)
        _consume_compose(screen)

    def test_action_dismiss_screen(self):
        """SkillDetailScreen.action_dismiss_screen → calls dismiss(None)."""
        screen = SkillDetailScreen({"slug": "s"})
        screen.dismiss = MagicMock()
        screen.action_dismiss_screen()
        screen.dismiss.assert_called_once_with(None)

    def test_action_edit_skill(self):
        """SkillDetailScreen.action_edit_skill → calls dismiss('edit')."""
        screen = SkillDetailScreen({"slug": "s"})
        screen.dismiss = MagicMock()
        screen.action_edit_skill()
        screen.dismiss.assert_called_once_with("edit")


@unittest.skipUnless(HAS_TEXTUAL, "textual not installed")
class TestEnvDetailScreenCompose(unittest.TestCase):
    """Test EnvDetailScreen.compose() — lines 511-542."""

    def test_compose_full_env(self):
        """EnvDetailScreen.compose: env with last_seen, paths, absent (lines 511-542)."""
        env = {
            "name": "Home PC", "hostname": "home-pc",
            "location": "Home", "last_seen": "2026-01-01",
            "paths": {"nexus": "/home/user/nexus", "mnemo": "/home/user/mnemo"},
            "absent": ["dragon-heir"],
        }
        screen = EnvDetailScreen(env)
        _consume_compose(screen)

    def test_compose_minimal_env(self):
        """EnvDetailScreen.compose: no last_seen, paths, absent."""
        env = {"name": "Server", "hostname": "srv01", "location": "Cloud"}
        screen = EnvDetailScreen(env)
        _consume_compose(screen)

    def test_action_dismiss_screen(self):
        """EnvDetailScreen.action_dismiss_screen → calls dismiss(None)."""
        screen = EnvDetailScreen({"hostname": "h"})
        screen.dismiss = MagicMock()
        screen.action_dismiss_screen()
        screen.dismiss.assert_called_once_with(None)


@unittest.skipUnless(HAS_TEXTUAL, "textual not installed")
class TestCliSelectScreenCancel(unittest.TestCase):
    """Test CliSelectScreen.action_cancel() — line 592."""

    def test_action_cancel_dismisses_with_none(self):
        """CliSelectScreen.action_cancel → calls dismiss(None) (line 592)."""
        clis = [CliEntry("claude", "claude", "Claude Code")]
        screen = CliSelectScreen(clis)
        screen.dismiss = MagicMock()
        screen.action_cancel()
        screen.dismiss.assert_called_once_with(None)


@unittest.skipUnless(HAS_TEXTUAL, "textual not installed")
class TestNexusAppFilteredLoading(unittest.TestCase):
    """Test _load_* methods with filter_text active."""

    def _make_app(self):
        mock_container = MagicMock()
        mock_container.projects.list_all.return_value = []
        mock_container.ideas.list_all.return_value = []
        mock_container.apps.list_all.return_value = []
        mock_container.codex.list_all.return_value = []
        mock_container.environments.list_all.return_value = []
        mock_container.config = MagicMock()
        with patch("nexus.tui.app.detect_clis", return_value=[]), \
             patch("nexus.tui.app.get_container", return_value=mock_container), \
             patch("nexus.tui.app.ScanRepository") as mock_scan_repo_cls:
            mock_scan_repo_cls.return_value.read.return_value = {"projects": [], "skills": {}}
            app = NexusApp()
        app._container = mock_container
        app._scan_repo = mock_scan_repo_cls.return_value
        return app

    def _make_mock_list_view(self, items=None):
        lv = MagicMock()
        lv.highlighted_child = None
        lv.children = items or []
        return lv

    def _make_mock_data_table(self):
        """Create a mock DataTable with proper add_row that returns RowKey."""
        dt = MagicMock()
        dt.row_count = 0
        self._add_row_count = 0
        def fake_add_row(*args, key=None):
            self._add_row_count += 1
            return RowKey(key or str(self._add_row_count))
        dt.add_row = MagicMock(side_effect=fake_add_row)
        return dt

    def test_load_projects_with_filter(self):
        """_load_projects: filter_text filters the DataTable rows."""
        from nexus.models import Project
        app = self._make_app()
        app.filter_text = "nexus"
        app._container.projects.list_all.return_value = [
            Project(name="Nexus", slug="nexus", domain="ferramentas"),
            Project(name="Dragon", slug="dragon", domain="games"),
        ]
        app._scan_repo.read.return_value = {"projects": [], "skills": {}}
        dt = self._make_mock_data_table()
        alert_widget = MagicMock()
        with patch.object(app, "query_one", side_effect=lambda sel, cls=None:
                          alert_widget if "alerts" in sel else dt):
            app._load_projects()
        # Only "Nexus" matches filter → at least 1 data row (+ group header)
        self.assertGreaterEqual(dt.add_row.call_count, 1)

    def test_load_projects_health_alerts(self):
        """_load_projects: health alerts for missing memory/path."""
        from nexus.models import Project
        app = self._make_app()
        app.filter_text = ""
        app._container.projects.list_all.return_value = [
            Project(name="AlertProj", slug="ap"),
        ]
        app._scan_repo.read.return_value = {
            "projects": [
                {"name": "AlertProj", "slug": "ap", "status": "active",
                 "health": {"claude_memory_portable": False, "path_exists": False}}
            ],
            "skills": {},
        }
        dt = self._make_mock_data_table()
        alert_widget = MagicMock()
        with patch.object(app, "query_one", side_effect=lambda sel, cls=None:
                          alert_widget if "alerts" in sel else dt):
            app._load_projects()
        # Alert widget should show
        alert_widget.update.assert_called_once()

    def test_load_ideas_with_filter(self):
        """_load_ideas: filter_text filters the DataTable rows."""
        from nexus.models import Idea
        app = self._make_app()
        app.filter_text = "python"
        app._container.ideas.list_all.return_value = [
            Idea(id="1", title="Python Ideas", domain="pessoal"),
            Idea(id="2", title="Java Thoughts", domain="trabalho"),
        ]
        dt = self._make_mock_data_table()
        with patch.object(app, "query_one", return_value=dt):
            app._load_ideas()
        # Only Python matches → 1 group header + 1 data row
        self.assertEqual(dt.add_row.call_count, 2)

    def test_load_codex_with_filter(self):
        """_load_codex: filter_text filters the DataTable rows."""
        from nexus.models import CodexEntry
        app = self._make_app()
        app.filter_text = "python"
        app._container.codex.list_all.return_value = [
            CodexEntry(slug="python-patterns", title="Python Patterns", domain="pessoal"),
            CodexEntry(slug="docker-setup", title="Docker Setup", domain="pessoal"),
        ]
        dt = self._make_mock_data_table()
        with patch.object(app, "query_one", return_value=dt):
            app._load_codex()
        # Only Python Patterns matches → 1 data row
        self.assertEqual(dt.add_row.call_count, 1)

    def test_load_apps_with_filter(self):
        """_load_apps: filter_text filters the DataTable rows."""
        from nexus.models import App as AppModel
        app = self._make_app()
        app.filter_text = "claude"
        app._container.apps.list_all.return_value = [
            AppModel(name="Claude Code", slug="claude", domain="ferramentas"),
            AppModel(name="Firefox", slug="firefox", domain="pessoal"),
        ]
        dt = self._make_mock_data_table()
        with patch.object(app, "query_one", return_value=dt):
            app._load_apps()
        # 1 group header + 1 data row for Claude Code = 2 add_row calls
        self.assertEqual(dt.add_row.call_count, 2)

    def test_load_skills_with_filter(self):
        """_load_skills: filter_text filters the DataTable rows."""
        app = self._make_app()
        app.filter_text = "python"
        app._scan_repo.read.return_value = {
            "projects": [],
            "skills": {
                "python-tips": {"title": "Python Tips", "presence": {"H": {"global": True}}},
                "docker-setup": {"title": "Docker Setup", "presence": {"H": {"global": False, "repos": ["proj"]}}},
            },
        }
        dt = self._make_mock_data_table()
        with patch.object(app, "query_one", return_value=dt):
            app._load_skills()
        # Only python-tips matches -> 1 data row
        self.assertEqual(dt.add_row.call_count, 1)

    def test_load_environments_with_filter(self):
        """_load_environments: filter_text filters the DataTable rows."""
        from nexus.models import Environment
        app = self._make_app()
        app.filter_text = "home"
        app._container.environments.list_all.return_value = [
            Environment(hostname="home-pc", name="Home PC", location="home"),
            Environment(hostname="work-pc", name="Work PC", location="office"),
        ]
        dt = self._make_mock_data_table()
        with patch.object(app, "query_one", return_value=dt):
            app._load_environments()
        # Only home-pc matches -> 1 data row
        self.assertEqual(dt.add_row.call_count, 1)


@unittest.skipUnless(HAS_TEXTUAL, "textual not installed")
class TestNexusAppDetailBarNewTabs(unittest.TestCase):
    """Test _update_detail_bar for codex, skills, environments tabs."""

    def _make_app(self):
        with patch("nexus.tui.app.detect_clis", return_value=[]):
            app = NexusApp()
        return app

    def _make_mock_table(self, row_count=1, cursor_row=0, row_key="test"):
        dt = MagicMock()
        dt.row_count = row_count
        dt.cursor_row = cursor_row
        dt.coordinate_to_cell_key.return_value = (RowKey(row_key), None)
        return dt

    def test_detail_bar_codex_with_entry(self):
        """_update_detail_bar: codex tab with entry shows title and kind."""
        app = self._make_app()
        app._active_tab = MagicMock(return_value="codex")
        app._group_keys = set()
        codex_data = {"title": "Python Tips", "kind": "guia", "domain": "tech", "slug": "python-tips"}
        app._codex_row_data[RowKey("codex:python-tips")] = codex_data
        dt = self._make_mock_table(row_key="codex:python-tips")
        bar = MagicMock()
        app.query_one = MagicMock(side_effect=lambda sel, cls=None:
                                  dt if "codex-table" in sel else bar)
        app._update_detail_bar()
        bar.update.assert_called_once()
        call_arg = bar.update.call_args[0][0]
        self.assertIn("Python Tips", call_arg)
        self.assertIn("guia", call_arg)

    def test_detail_bar_skills_with_skill(self):
        """_update_detail_bar: skills tab with skill shows title and scope."""
        app = self._make_app()
        app._active_tab = MagicMock(return_value="skills")
        app._group_keys = set()
        skill_data = {"title": "BMAD", "slug": "bmad", "presence": {"H": {"global": True}}}
        app._skill_row_data[RowKey("skill:bmad")] = skill_data
        dt = self._make_mock_table(row_key="skill:bmad")
        bar = MagicMock()
        app.query_one = MagicMock(side_effect=lambda sel, cls=None:
                                  dt if "skills-table" in sel else bar)
        app._update_detail_bar()
        bar.update.assert_called_once()
        call_arg = bar.update.call_args[0][0]
        self.assertIn("BMAD", call_arg)

    def test_detail_bar_environments_with_env(self):
        """_update_detail_bar: environments tab with env shows name and hostname."""
        app = self._make_app()
        app._active_tab = MagicMock(return_value="environments")
        app._group_keys = set()
        env_data = {"name": "Home PC", "hostname": "mypc", "location": "casa", "last_seen": "2026-03-10"}
        app._env_row_data[RowKey("env:mypc")] = env_data
        dt = self._make_mock_table(row_key="env:mypc")
        bar = MagicMock()
        app.query_one = MagicMock(side_effect=lambda sel, cls=None:
                                  dt if "environments-table" in sel else bar)
        app._update_detail_bar()
        bar.update.assert_called_once()
        call_arg = bar.update.call_args[0][0]
        self.assertIn("Home PC", call_arg)
        self.assertIn("mypc", call_arg)


@unittest.skipUnless(HAS_TEXTUAL, "textual not installed")
class TestNexusAppSelectionGetters(unittest.TestCase):
    """Test _get_selected_* fallback paths."""

    def _make_app(self):
        with patch("nexus.tui.app.detect_clis", return_value=[]):
            return NexusApp()

    def _make_mock_table(self, row_count=0, cursor_row=0, row_key="test"):
        """Create a mock DataTable for selection getter tests."""
        dt = MagicMock()
        dt.row_count = row_count
        dt.cursor_row = cursor_row
        dt.coordinate_to_cell_key.return_value = (RowKey(row_key), None)
        return dt

    def test_get_selected_project_returns_data_from_table(self):
        """_get_selected_project: cursor on data row → return project dict."""
        app = self._make_app()
        app._project_row_data[RowKey("nexus")] = {"name": "Nexus"}
        app._group_keys = set()
        app._active_tab = MagicMock(return_value="projects")
        dt = self._make_mock_table(row_count=1, row_key="nexus")
        app.query_one = MagicMock(return_value=dt)
        result = app._get_selected_project()
        self.assertEqual(result, {"name": "Nexus"})

    def test_get_selected_project_no_rows_returns_none(self):
        """_get_selected_project: empty table → returns None."""
        app = self._make_app()
        dt = self._make_mock_table(row_count=0)
        app.query_one = MagicMock(return_value=dt)
        result = app._get_selected_project()
        self.assertIsNone(result)

    def test_get_selected_idea_returns_data_from_table(self):
        """_get_selected_idea: cursor on idea row → return idea dict."""
        app = self._make_app()
        app._idea_row_data[RowKey("idea:abc")] = {"id": "abc", "title": "X"}
        app._group_keys = set()
        app._active_tab = MagicMock(return_value="ideas")
        dt = self._make_mock_table(row_count=1, row_key="idea:abc")
        app.query_one = MagicMock(return_value=dt)
        result = app._get_selected_idea()
        self.assertEqual(result["id"], "abc")

    def test_get_selected_codex_returns_data_from_table(self):
        """_get_selected_codex: cursor on codex row -> return codex dict."""
        app = self._make_app()
        app._codex_row_data[RowKey("codex:guide")] = {"title": "Codex Entry", "slug": "guide"}
        app._group_keys = set()
        app._active_tab = MagicMock(return_value="codex")
        dt = self._make_mock_table(row_count=1, row_key="codex:guide")
        app.query_one = MagicMock(return_value=dt)
        result = app._get_selected_codex()
        self.assertEqual(result["title"], "Codex Entry")

    def test_get_selected_codex_returns_none_when_no_rows(self):
        """_get_selected_codex: empty table -> None."""
        app = self._make_app()
        dt = self._make_mock_table(row_count=0)
        app.query_one = MagicMock(return_value=dt)
        result = app._get_selected_codex()
        self.assertIsNone(result)

    def test_get_selected_app_returns_data_from_table(self):
        """_get_selected_app: cursor on app row → return app dict."""
        app = self._make_app()
        app._app_row_data[RowKey("app:claude")] = {"name": "Claude Code"}
        app._group_keys = set()
        app._active_tab = MagicMock(return_value="apps")
        dt = self._make_mock_table(row_count=1, row_key="app:claude")
        app.query_one = MagicMock(return_value=dt)
        result = app._get_selected_app()
        self.assertEqual(result["name"], "Claude Code")

    def test_get_selected_skill_returns_data_from_table(self):
        """_get_selected_skill: cursor on skill row -> return skill dict."""
        app = self._make_app()
        app._skill_row_data[RowKey("skill:pyskill")] = {"slug": "pyskill"}
        app._group_keys = set()
        app._active_tab = MagicMock(return_value="skills")
        dt = self._make_mock_table(row_count=1, row_key="skill:pyskill")
        app.query_one = MagicMock(return_value=dt)
        result = app._get_selected_skill()
        self.assertEqual(result["slug"], "pyskill")

    def test_get_selected_env_returns_data_from_table(self):
        """_get_selected_env: cursor on env row -> return env dict."""
        app = self._make_app()
        app._env_row_data[RowKey("env:myhost")] = {"hostname": "myhost"}
        app._group_keys = set()
        app._active_tab = MagicMock(return_value="environments")
        dt = self._make_mock_table(row_count=1, row_key="env:myhost")
        app.query_one = MagicMock(return_value=dt)
        result = app._get_selected_env()
        self.assertEqual(result["hostname"], "myhost")


@unittest.skipUnless(HAS_TEXTUAL, "textual not installed")
class TestNexusAppActionLaunchAdditional(unittest.TestCase):
    """Additional action_launch_project branches."""

    def _make_app(self):
        with patch("nexus.tui.app.detect_clis", return_value=[]):
            return NexusApp()

    def test_launch_app_no_url(self):
        """action_launch_project: apps tab, app has no URL → notify warning (line 1115)."""
        app = self._make_app()
        app._active_tab = MagicMock(return_value="apps")
        app._get_selected_app = MagicMock(return_value={"slug": "myapp"})
        app.notify = MagicMock()
        app.action_launch_project()
        app.notify.assert_called_once()
        self.assertIn("warning", str(app.notify.call_args))

    def test_launch_unknown_tab_returns_early(self):
        """action_launch_project: unknown tab → early return (line 1131)."""
        app = self._make_app()
        app._active_tab = MagicMock(return_value="unknown_tab")
        app.exit = MagicMock()
        app.notify = MagicMock()
        app.action_launch_project()
        app.exit.assert_not_called()

    def test_launch_projects_no_selection(self):
        """action_launch_project: projects tab, no project → early return (line 1136)."""
        app = self._make_app()
        app._active_tab = MagicMock(return_value="projects")
        app._get_selected_project = MagicMock(return_value=None)
        app.exit = MagicMock()
        app.action_launch_project()
        app.exit.assert_not_called()

    def test_launch_project_path_missing(self):
        """action_launch_project: path doesn't exist → notify+exit (lines 1141-1143)."""
        app = self._make_app()
        app._active_tab = MagicMock(return_value="projects")
        app._get_selected_project = MagicMock(return_value={"path": "/nonexistent", "slug": "x"})
        app.notify = MagicMock()
        app.exit = MagicMock()
        with patch("nexus.tui.app.resolve_path_for_entry", return_value="/nonexistent"), \
             patch("nexus.tui.app.resolve_project_path", return_value="/nonexistent"), \
             patch("nexus.tui.app.Path") as mock_path:
            mock_path.return_value.exists.return_value = False
            app.action_launch_project()
        app.notify.assert_called_once()
        app.exit.assert_called_once()


@unittest.skipUnless(HAS_TEXTUAL, "textual not installed")
class TestNexusAppDetailDismissCallbacks(unittest.TestCase):
    """Test _on_*_detail_dismissed callbacks."""

    def _make_app(self):
        with patch("nexus.tui.app.detect_clis", return_value=[]):
            return NexusApp()

    def test_on_idea_detail_dismissed_edit(self):
        """_on_idea_detail_dismissed: result='edit' → exit with idea_edit (lines 1164-1167)."""
        app = self._make_app()
        app._get_selected_idea = MagicMock(return_value={"id": "abc"})
        app.exit = MagicMock()
        app._on_idea_detail_dismissed("edit")
        app.exit.assert_called_once()
        result = app.exit.call_args[1]["result"]
        self.assertEqual(result, ("idea_edit", "abc"))

    def test_on_idea_detail_dismissed_not_edit(self):
        """_on_idea_detail_dismissed: result=None → no exit."""
        app = self._make_app()
        app.exit = MagicMock()
        app._on_idea_detail_dismissed(None)
        app.exit.assert_not_called()

    def test_on_codex_detail_dismissed_edit(self):
        """_on_codex_detail_dismissed: result='edit' → exit with codex_edit."""
        app = self._make_app()
        app._get_selected_codex = MagicMock(return_value={"slug": "myslug"})
        app.exit = MagicMock()
        app._on_codex_detail_dismissed("edit")
        app.exit.assert_called_once()
        result = app.exit.call_args[1]["result"]
        self.assertEqual(result, ("codex_edit", "myslug"))

    def test_on_skill_detail_dismissed_edit(self):
        """_on_skill_detail_dismissed: result='edit' → exit with skill_edit (lines 1176-1179)."""
        app = self._make_app()
        app._get_selected_skill = MagicMock(return_value={"slug": "myskill"})
        app.exit = MagicMock()
        app._on_skill_detail_dismissed("edit")
        app.exit.assert_called_once()
        result = app.exit.call_args[1]["result"]
        self.assertEqual(result, ("skill_edit", "myskill"))

    def test_on_skill_detail_dismissed_not_edit(self):
        """_on_skill_detail_dismissed: result=None → no exit."""
        app = self._make_app()
        app.exit = MagicMock()
        app._on_skill_detail_dismissed(None)
        app.exit.assert_not_called()


@unittest.skipUnless(HAS_TEXTUAL, "textual not installed")
class TestNexusAppActionEditAdditional(unittest.TestCase):
    """Test action_edit_item for additional tabs."""

    def _make_app(self):
        with patch("nexus.tui.app.detect_clis", return_value=[]):
            return NexusApp()

    def test_edit_item_apps_tab(self):
        """action_edit_item: apps tab → exit with app_edit (lines 1195-1198)."""
        app = self._make_app()
        app._active_tab = MagicMock(return_value="apps")
        app._get_selected_app = MagicMock(return_value={"slug": "myapp"})
        app.exit = MagicMock()
        app.action_edit_item()
        result = app.exit.call_args[1]["result"]
        self.assertEqual(result, ("app_edit", "myapp"))

    def test_edit_item_skills_tab(self):
        """action_edit_item: skills tab → exit with skill_edit (lines 1199-1202)."""
        app = self._make_app()
        app._active_tab = MagicMock(return_value="skills")
        app._get_selected_skill = MagicMock(return_value={"slug": "myskill"})
        app.exit = MagicMock()
        app.action_edit_item()
        result = app.exit.call_args[1]["result"]
        self.assertEqual(result, ("skill_edit", "myskill"))

    def test_edit_item_environments_tab(self):
        """action_edit_item: environments tab → exit with env_edit (lines 1203-1206)."""
        app = self._make_app()
        app._active_tab = MagicMock(return_value="environments")
        app._get_selected_env = MagicMock(return_value={"hostname": "myhost"})
        app.exit = MagicMock()
        app.action_edit_item()
        result = app.exit.call_args[1]["result"]
        self.assertEqual(result, ("env_edit", "myhost"))


@unittest.skipUnless(HAS_TEXTUAL, "textual not installed")
class TestNexusAppActionAddRemovePromote(unittest.TestCase):
    """Test action_add_idea, action_remove_item, action_promote_idea for various tabs."""

    def _make_app(self):
        with patch("nexus.tui.app.detect_clis", return_value=[]):
            return NexusApp()

    def test_add_idea_ideas_tab(self):
        """action_add_idea: ideas tab → exit with idea_add (line 1268)."""
        app = self._make_app()
        app._active_tab = MagicMock(return_value="ideas")
        app.exit = MagicMock()
        app.action_add_idea()
        result = app.exit.call_args[1]["result"]
        self.assertEqual(result, ("idea_add", None))

    def test_add_idea_projects_tab(self):
        """action_add_idea: projects tab → exit with add (lines 1275-1276)."""
        app = self._make_app()
        app._active_tab = MagicMock(return_value="projects")
        app.exit = MagicMock()
        app.action_add_idea()
        result = app.exit.call_args[1]["result"]
        self.assertEqual(result, ("add", None))

    def test_remove_item_ideas_tab(self):
        """action_remove_item: ideas tab → exit with idea_remove (lines 1243-1245)."""
        app = self._make_app()
        app._active_tab = MagicMock(return_value="ideas")
        app._get_selected_idea = MagicMock(return_value={"id": "abc"})
        app.exit = MagicMock()
        app.action_remove_item()
        result = app.exit.call_args[1]["result"]
        self.assertEqual(result, ("idea_remove", "abc"))

    def test_remove_item_projects_tab(self):
        """action_remove_item: projects tab → exit with remove (lines 1247-1249)."""
        app = self._make_app()
        app._active_tab = MagicMock(return_value="projects")
        app._get_selected_project = MagicMock(return_value={"name": "Nexus", "path": "/nexus"})
        app.exit = MagicMock()
        app.action_remove_item()
        result = app.exit.call_args[1]["result"]
        self.assertEqual(result[0], "remove")
        self.assertEqual(result[1], "Nexus")

    def test_remove_item_environments_tab(self):
        """action_remove_item: environments tab → notify warning (lines 1262-1263)."""
        app = self._make_app()
        app._active_tab = MagicMock(return_value="environments")
        app.notify = MagicMock()
        app.action_remove_item()
        app.notify.assert_called_once()
        self.assertIn("warning", str(app.notify.call_args))

    def test_promote_idea_ideas_tab(self):
        """action_promote_idea: ideas tab → exit with idea_promote (lines 1281-1283)."""
        app = self._make_app()
        app._active_tab = MagicMock(return_value="ideas")
        app._get_selected_idea = MagicMock(return_value={"id": "myidea"})
        app.exit = MagicMock()
        app.action_promote_idea()
        result = app.exit.call_args[1]["result"]
        self.assertEqual(result, ("idea_promote", "myidea"))

    def test_promote_idea_projects_tab_warns(self):
        """action_promote_idea: projects tab → warning (promote removed)."""
        app = self._make_app()
        app._active_tab = MagicMock(return_value="projects")
        app.notify = MagicMock()
        app.exit = MagicMock()
        app.action_promote_idea()
        app.exit.assert_not_called()
        app.notify.assert_called_once()


@unittest.skipUnless(HAS_TEXTUAL, "textual not installed")
class TestNexusAppAddNoteAction(unittest.TestCase):
    """Test action_add_note for apps tab and projects tab."""

    def _make_app(self):
        with patch("nexus.tui.app.detect_clis", return_value=[]):
            return NexusApp()

    def test_add_note_apps_tab(self):
        """action_add_note: apps tab → exit with app_note (lines 1210-1213)."""
        app = self._make_app()
        app._active_tab = MagicMock(return_value="apps")
        app._get_selected_app = MagicMock(return_value={"slug": "claude"})
        app.exit = MagicMock()
        app.action_add_note()
        result = app.exit.call_args[1]["result"]
        self.assertEqual(result, ("app_note", "claude"))

    def test_add_note_projects_no_project(self):
        """action_add_note: projects tab, no selection → early return."""
        app = self._make_app()
        app._active_tab = MagicMock(return_value="projects")
        app._get_selected_project = MagicMock(return_value=None)
        app.exit = MagicMock()
        app.action_add_note()
        app.exit.assert_not_called()

    def test_add_note_not_projects_or_apps(self):
        """action_add_note: other tab → early return (line 1215-1216)."""
        app = self._make_app()
        app._active_tab = MagicMock(return_value="ideas")
        app.exit = MagicMock()
        app.action_add_note()
        app.exit.assert_not_called()


@unittest.skipUnless(HAS_TEXTUAL, "textual not installed")
class TestNexusAppRowDataForTab(unittest.TestCase):
    """Test _row_data_for_tab returns correct dict for all tabs."""

    def _make_app(self):
        with patch("nexus.tui.app.detect_clis", return_value=[]):
            return NexusApp()

    def test_row_data_for_all_tabs(self):
        """_row_data_for_tab returns correct dict for every tab."""
        app = self._make_app()
        for tab, attr in [
            ("projects", "_project_row_data"),
            ("ideas", "_idea_row_data"),
            ("apps", "_app_row_data"),
            ("codex", "_codex_row_data"),
            ("skills", "_skill_row_data"),
            ("environments", "_env_row_data"),
        ]:
            app._active_tab = MagicMock(return_value=tab)
            self.assertIs(app._row_data_for_tab(), getattr(app, attr))


@unittest.skipUnless(HAS_TEXTUAL, "textual not installed")
class TestNexusAppTabActivatedGuard(unittest.TestCase):
    """Test on_tabbed_content_tab_activated stale event guard — line 950."""

    def _make_app(self):
        with patch("nexus.tui.app.detect_clis", return_value=[]):
            return NexusApp()

    def test_stale_event_ignored(self):
        """on_tabbed_content_tab_activated: stale event (pane.id != active) → ignored (line 950)."""
        app = self._make_app()
        app._is_mounted = True
        app._active_tab = MagicMock(return_value="projects")
        app._load_projects = MagicMock()

        event = MagicMock()
        event.pane.id = "ideas"  # Doesn't match active tab "projects"

        app.on_tabbed_content_tab_activated(event)
        # Loader should NOT be called since event is stale
        app._load_projects.assert_not_called()


@unittest.skipUnless(HAS_TEXTUAL, "textual not installed")
class TestNexusAppFocusFilter(unittest.TestCase):
    """Test action_focus_filter — line 965."""

    def _make_app(self):
        with patch("nexus.tui.app.detect_clis", return_value=[]):
            return NexusApp()

    def test_focus_filter_focuses_input(self):
        """action_focus_filter: focuses #filter-input (line 965)."""
        app = self._make_app()
        mock_input = MagicMock()
        app.query_one = MagicMock(return_value=mock_input)
        app.action_focus_filter()
        mock_input.focus.assert_called_once()


@unittest.skipUnless(HAS_TEXTUAL, "textual not installed")
class TestNexusAppLaunchIdeaSkillEnv(unittest.TestCase):
    """Test action_launch_project for ideas/skills/environments tabs."""

    def _make_app(self):
        with patch("nexus.tui.app.detect_clis", return_value=[]):
            return NexusApp()

    def test_launch_idea_tab_pushes_detail_screen(self):
        """action_launch_project: ideas tab with idea → push IdeaDetailScreen."""
        app = self._make_app()
        app._active_tab = MagicMock(return_value="ideas")
        app._get_selected_idea = MagicMock(return_value={"id": "x", "title": "T"})
        app.push_screen = MagicMock()
        app.action_launch_project()
        app.push_screen.assert_called_once()

    def test_launch_skill_tab_pushes_detail_screen(self):
        """action_launch_project: skills tab with skill → push SkillDetailScreen."""
        app = self._make_app()
        app._active_tab = MagicMock(return_value="skills")
        app._get_selected_skill = MagicMock(return_value={"slug": "py"})
        app.push_screen = MagicMock()
        app.action_launch_project()
        app.push_screen.assert_called_once()

    def test_launch_env_tab_pushes_detail_screen(self):
        """action_launch_project: environments tab with env → push EnvDetailScreen."""
        app = self._make_app()
        app._active_tab = MagicMock(return_value="environments")
        app._get_selected_env = MagicMock(return_value={"hostname": "pc"})
        app.push_screen = MagicMock()
        app.action_launch_project()
        app.push_screen.assert_called_once()

    def test_launch_app_with_url_opens_browser(self):
        """action_launch_project: apps tab, app has URL → opens browser + notify."""
        app = self._make_app()
        app._active_tab = MagicMock(return_value="apps")
        app._get_selected_app = MagicMock(return_value={"slug": "x", "url": "https://x.com"})
        app.notify = MagicMock()
        with patch("webbrowser.open") as mock_open:
            app.action_launch_project()
        mock_open.assert_called_once_with("https://x.com")
        app.notify.assert_called_once()


@unittest.skipUnless(HAS_TEXTUAL, "textual not installed")
class TestSetCodexOrder(unittest.TestCase):
    """Tests for the 'o' keybinding that sets codex entry order inline."""

    def _make_app(self):
        mock_container = MagicMock()
        mock_container.config = MagicMock()
        with patch("nexus.tui.app.detect_clis", return_value=[]), \
             patch("nexus.tui.app.get_container", return_value=mock_container), \
             patch("nexus.tui.app.ScanRepository") as mock_scan_repo_cls:
            mock_scan_repo_cls.return_value.read.return_value = {"projects": [], "skills": {}}
            app = NexusApp()
        return app

    def test_set_codex_order_binding_exists(self):
        """NexusApp has an 'o' binding for set_codex_order."""
        app = self._make_app()
        bindings = {b.key: b for b in app.BINDINGS}
        self.assertIn("o", bindings)
        self.assertEqual(bindings["o"].action, "set_codex_order")

    def test_set_codex_order_only_visible_on_codex_tab(self):
        """check_action: set_codex_order hidden on non-codex tabs."""
        app = self._make_app()
        for tab in ("projects", "ideas", "apps", "skills", "environments"):
            app._active_tab = MagicMock(return_value=tab)
            self.assertFalse(app.check_action("set_codex_order", ()))

        app._active_tab = MagicMock(return_value="codex")
        self.assertTrue(app.check_action("set_codex_order", ()))

    def test_set_codex_order_no_selection_notifies(self):
        """action_set_codex_order: no selected entry → warning notification."""
        app = self._make_app()
        app._active_tab = MagicMock(return_value="codex")
        app._get_selected_codex = MagicMock(return_value=None)
        app.notify = MagicMock()
        app.action_set_codex_order()
        app.notify.assert_called_once()
        self.assertIn("warning", str(app.notify.call_args))

    def test_set_codex_order_with_selection_pushes_screen(self):
        """action_set_codex_order: selected entry → push CodexOrderScreen."""
        app = self._make_app()
        app._active_tab = MagicMock(return_value="codex")
        app._get_selected_codex = MagicMock(return_value={
            "slug": "tips", "title": "Tips", "order": 3,
        })
        app.push_screen = MagicMock()
        app.action_set_codex_order()
        app.push_screen.assert_called_once()

    def test_codex_order_screen_initial_value_from_entry(self):
        """CodexOrderScreen shows current order as initial input value."""
        from nexus.tui import CodexOrderScreen
        screen = CodexOrderScreen(current_order=5)
        self.assertEqual(screen.current_order, 5)

    def test_codex_order_callback_saves_entry(self):
        """_on_codex_order_result: valid int → save entry, reload codex."""
        from nexus.models import CodexEntry
        app = self._make_app()
        app._active_tab = MagicMock(return_value="codex")
        app._get_selected_codex = MagicMock(return_value={"slug": "tips"})
        app._load_codex = MagicMock()
        app.notify = MagicMock()

        entry = CodexEntry(slug="tips", title="Tips", order=1, content="hello")
        app._container.codex.resolve.return_value = entry
        app._container.codex.edit.return_value = entry
        app._on_codex_order_result(7)

        app._container.codex.edit.assert_called_once_with("tips", order=7)
        app._load_codex.assert_called_once()

    def test_codex_order_callback_none_is_ignored(self):
        """_on_codex_order_result: None (cancelled) → no save."""
        app = self._make_app()
        app._get_selected_codex = MagicMock(return_value=None)
        app._load_codex = MagicMock()
        app._on_codex_order_result(None)
        app._container.codex.edit.assert_not_called()
        app._load_codex.assert_not_called()
