"""
TUI coverage gap tests — batch 2.

Targets remaining uncovered lines in nexus/tui.py:
  1035     — _get_selected_project: highlighted_child IS set → return its data
  1044     — _get_selected_idea: highlighted_child IS set → return its data
  1048     — _get_selected_idea: no match → None
  1053     — _get_selected_codex: highlighted_child IS set
  1062     — _get_selected_app: highlighted_child IS set
  1066     — _get_selected_app: no match → None
  1071     — _get_selected_skill: highlighted_child IS set
  1075     — _get_selected_skill: no match → None
  1080     — _get_selected_env: highlighted_child IS set
  1084     — _get_selected_env: no match → None
  1184-1186 — action_edit_item: ideas tab, idea selected → exit
  1188-1190 — action_edit_item: projects tab, project selected → exit
  1220     — action_add_note: projects tab, proj selected → exit
  1223-1238 — action_open_web: projects tab (url, route, neither)
  929-941  — on_input_changed: various tabs with filter text
  735-738  — _background_scan: progress callback
  745, 748, 751 — _background_scan: scan_cancelled checks
"""
import unittest
from unittest.mock import MagicMock, patch, call

try:
    from nexus.cli_registry import CliEntry
    from nexus.tui import NexusApp
    from textual.widgets.data_table import RowKey
    HAS_TEXTUAL = True
except ImportError:
    HAS_TEXTUAL = False


@unittest.skipUnless(HAS_TEXTUAL, "textual not installed")
class TestSelectionGettersHighlightedChild(unittest.TestCase):
    """Test _get_selected_* when data IS present."""

    def _make_app(self):
        with patch("nexus.tui.app.detect_clis", return_value=[]):
            return NexusApp()

    def _make_mock_table(self, row_count=1, cursor_row=0, row_key="test"):
        """Create a mock DataTable for selection getter tests."""
        dt = MagicMock()
        dt.row_count = row_count
        dt.cursor_row = cursor_row
        dt.coordinate_to_cell_key.return_value = (RowKey(row_key), None)
        return dt

    def test_get_selected_project_highlighted(self):
        """_get_selected_project: cursor on data row → return project dict."""
        app = self._make_app()
        app._project_row_data[RowKey("nexus")] = {"name": "Highlighted"}
        app._group_keys = set()
        app._active_tab = MagicMock(return_value="projects")
        dt = self._make_mock_table(row_key="nexus")
        app.query_one = MagicMock(return_value=dt)
        result = app._get_selected_project()
        self.assertEqual(result, {"name": "Highlighted"})

    def test_get_selected_idea_highlighted(self):
        """_get_selected_idea: cursor on idea row → return idea dict."""
        app = self._make_app()
        app._idea_row_data[RowKey("idea:hi")] = {"id": "highlighted-idea"}
        app._group_keys = set()
        app._active_tab = MagicMock(return_value="ideas")
        dt = self._make_mock_table(row_key="idea:hi")
        app.query_one = MagicMock(return_value=dt)
        result = app._get_selected_idea()
        self.assertEqual(result["id"], "highlighted-idea")

    def test_get_selected_idea_no_match_returns_none(self):
        """_get_selected_idea: empty table → None."""
        app = self._make_app()
        dt = self._make_mock_table(row_count=0)
        app.query_one = MagicMock(return_value=dt)
        result = app._get_selected_idea()
        self.assertIsNone(result)

    def test_get_selected_codex_highlighted(self):
        """_get_selected_codex: cursor on codex row -> return codex dict."""
        app = self._make_app()
        app._codex_row_data[RowKey("codex:guide")] = {"title": "Highlighted Codex", "slug": "guide"}
        app._group_keys = set()
        app._active_tab = MagicMock(return_value="codex")
        dt = self._make_mock_table(row_key="codex:guide")
        app.query_one = MagicMock(return_value=dt)
        result = app._get_selected_codex()
        self.assertEqual(result["title"], "Highlighted Codex")

    def test_get_selected_app_highlighted(self):
        """_get_selected_app: cursor on app row -> return app dict."""
        app = self._make_app()
        app._app_row_data[RowKey("app:claude")] = {"name": "Claude Code"}
        app._group_keys = set()
        app._active_tab = MagicMock(return_value="apps")
        dt = self._make_mock_table(row_key="app:claude")
        app.query_one = MagicMock(return_value=dt)
        result = app._get_selected_app()
        self.assertEqual(result["name"], "Claude Code")

    def test_get_selected_app_no_match_returns_none(self):
        """_get_selected_app: empty table -> None."""
        app = self._make_app()
        dt = self._make_mock_table(row_count=0)
        app.query_one = MagicMock(return_value=dt)
        result = app._get_selected_app()
        self.assertIsNone(result)

    def test_get_selected_skill_highlighted(self):
        """_get_selected_skill: cursor on skill row -> return skill dict."""
        app = self._make_app()
        app._skill_row_data[RowKey("skill:python-tips")] = {"slug": "python-tips"}
        app._group_keys = set()
        app._active_tab = MagicMock(return_value="skills")
        dt = self._make_mock_table(row_key="skill:python-tips")
        app.query_one = MagicMock(return_value=dt)
        result = app._get_selected_skill()
        self.assertEqual(result["slug"], "python-tips")

    def test_get_selected_skill_no_match(self):
        """_get_selected_skill: empty table -> None."""
        app = self._make_app()
        dt = self._make_mock_table(row_count=0)
        app.query_one = MagicMock(return_value=dt)
        result = app._get_selected_skill()
        self.assertIsNone(result)

    def test_get_selected_env_highlighted(self):
        """_get_selected_env: cursor on env row -> return env dict."""
        app = self._make_app()
        app._env_row_data[RowKey("env:myhost")] = {"hostname": "myhost"}
        app._group_keys = set()
        app._active_tab = MagicMock(return_value="environments")
        dt = self._make_mock_table(row_key="env:myhost")
        app.query_one = MagicMock(return_value=dt)
        result = app._get_selected_env()
        self.assertEqual(result["hostname"], "myhost")

    def test_get_selected_env_no_match(self):
        """_get_selected_env: empty table -> None."""
        app = self._make_app()
        dt = self._make_mock_table(row_count=0)
        app.query_one = MagicMock(return_value=dt)
        result = app._get_selected_env()
        self.assertIsNone(result)


@unittest.skipUnless(HAS_TEXTUAL, "textual not installed")
class TestActionEditItemIdeasProjects(unittest.TestCase):
    """Test action_edit_item for ideas and projects tabs (lines 1184-1190)."""

    def _make_app(self):
        with patch("nexus.tui.app.detect_clis", return_value=[]):
            return NexusApp()

    def test_edit_item_ideas_with_idea(self):
        """action_edit_item: ideas tab, idea selected → exit idea_edit (lines 1184-1186)."""
        app = self._make_app()
        app._active_tab = MagicMock(return_value="ideas")
        app._get_selected_idea = MagicMock(return_value={"id": "myidea"})
        app.exit = MagicMock()
        app.action_edit_item()
        result = app.exit.call_args[1]["result"]
        self.assertEqual(result, ("idea_edit", "myidea"))

    def test_edit_item_projects_with_project(self):
        """action_edit_item: projects tab, project selected → exit edit (lines 1188-1190)."""
        app = self._make_app()
        app._active_tab = MagicMock(return_value="projects")
        app._get_selected_project = MagicMock(return_value={"name": "Nexus", "path": "/nexus"})
        app.exit = MagicMock()
        app.action_edit_item()
        result = app.exit.call_args[1]["result"]
        self.assertEqual(result[0], "edit")
        self.assertEqual(result[1], "Nexus")

    def test_edit_item_codex_with_entry(self):
        """action_edit_item: codex tab, entry selected → exit codex_edit."""
        app = self._make_app()
        app._active_tab = MagicMock(return_value="codex")
        app._get_selected_codex = MagicMock(return_value={"slug": "myentry"})
        app.exit = MagicMock()
        app.action_edit_item()
        result = app.exit.call_args[1]["result"]
        self.assertEqual(result, ("codex_edit", "myentry"))


@unittest.skipUnless(HAS_TEXTUAL, "textual not installed")
class TestActionAddNoteProjects(unittest.TestCase):
    """Test action_add_note: projects tab with selection (line 1220)."""

    def _make_app(self):
        with patch("nexus.tui.app.detect_clis", return_value=[]):
            return NexusApp()

    def test_add_note_projects_with_project(self):
        """action_add_note: projects tab, project selected → exit note (line 1220)."""
        app = self._make_app()
        app._active_tab = MagicMock(return_value="projects")
        app._get_selected_project = MagicMock(return_value={"name": "MyProj", "path": "/myproj"})
        app.exit = MagicMock()
        app.action_add_note()
        result = app.exit.call_args[1]["result"]
        self.assertEqual(result[0], "note")
        self.assertEqual(result[1], "MyProj")


@unittest.skipUnless(HAS_TEXTUAL, "textual not installed")
class TestActionOpenWeb(unittest.TestCase):
    """Test action_open_web — lines 1223-1238."""

    def _make_app(self):
        with patch("nexus.tui.app.detect_clis", return_value=[]):
            return NexusApp()

    def test_open_web_not_projects_tab(self):
        """action_open_web: not projects/apps tab → warning notification."""
        app = self._make_app()
        app._active_tab = MagicMock(return_value="ideas")
        app.notify = MagicMock()
        app.action_open_web()
        app.notify.assert_called_once()
        self.assertIn("warning", str(app.notify.call_args))

    def test_open_web_no_selection(self):
        """action_open_web: projects tab, no project → early return."""
        app = self._make_app()
        app._active_tab = MagicMock(return_value="projects")
        app._get_selected_project = MagicMock(return_value=None)
        app.notify = MagicMock()
        app.action_open_web()
        app.notify.assert_not_called()

    def test_open_web_with_url(self):
        """action_open_web: project has URL → opens browser + notify (line 1231-1234)."""
        app = self._make_app()
        app._active_tab = MagicMock(return_value="projects")
        app._get_selected_project = MagicMock(return_value={"url": "https://example.com", "web": {}})
        app.notify = MagicMock()
        with patch("webbrowser.open") as mock_open:
            app.action_open_web()
        mock_open.assert_called_once_with("https://example.com")
        app.notify.assert_called_once()

    def test_open_web_with_route_no_url(self):
        """action_open_web: project has web route but no URL → warning (line 1235-1236)."""
        app = self._make_app()
        app._active_tab = MagicMock(return_value="projects")
        app._get_selected_project = MagicMock(return_value={"url": None, "web": {"route": "/myapp"}})
        app.notify = MagicMock()
        app.action_open_web()
        app.notify.assert_called_once()
        self.assertIn("warning", str(app.notify.call_args))

    def test_open_web_no_url_no_route(self):
        """action_open_web: no URL, no web route → warning (line 1237-1238)."""
        app = self._make_app()
        app._active_tab = MagicMock(return_value="projects")
        app._get_selected_project = MagicMock(return_value={"url": None, "web": None})
        app.notify = MagicMock()
        app.action_open_web()
        app.notify.assert_called_once()
        self.assertIn("warning", str(app.notify.call_args))


@unittest.skipUnless(HAS_TEXTUAL, "textual not installed")
class TestOnInputChanged(unittest.TestCase):
    """Test on_input_changed handler — lines 929-941."""

    def _make_app(self):
        with patch("nexus.tui.app.detect_clis", return_value=[]):
            return NexusApp()

    def _make_event(self, input_id, value):
        event = MagicMock()
        event.input.id = input_id
        event.value = value
        return event

    def test_input_changed_filter_input_ideas_tab(self):
        """on_input_changed: filter-input on ideas tab → calls _load_ideas (lines 929-941)."""
        app = self._make_app()
        app._active_tab = MagicMock(return_value="ideas")
        app._load_ideas = MagicMock()
        event = self._make_event("filter-input", "python")
        app.on_input_changed(event)
        self.assertEqual(app.filter_text, "python")
        app._load_ideas.assert_called_once()

    def test_input_changed_filter_input_projects_tab(self):
        """on_input_changed: filter-input on projects tab → calls _load_projects."""
        app = self._make_app()
        app._active_tab = MagicMock(return_value="projects")
        app._load_projects = MagicMock()
        event = self._make_event("filter-input", "nexus")
        app.on_input_changed(event)
        app._load_projects.assert_called_once()

    def test_input_changed_filter_input_skills_tab(self):
        """on_input_changed: filter-input on skills tab → calls _load_skills."""
        app = self._make_app()
        app._active_tab = MagicMock(return_value="skills")
        app._load_skills = MagicMock()
        event = self._make_event("filter-input", "python")
        app.on_input_changed(event)
        app._load_skills.assert_called_once()

    def test_input_changed_filter_input_environments_tab(self):
        """on_input_changed: filter-input on environments tab → calls _load_environments."""
        app = self._make_app()
        app._active_tab = MagicMock(return_value="environments")
        app._load_environments = MagicMock()
        event = self._make_event("filter-input", "home")
        app.on_input_changed(event)
        app._load_environments.assert_called_once()

    def test_input_changed_filter_input_codex_tab(self):
        """on_input_changed: filter-input on codex tab → calls _load_codex."""
        app = self._make_app()
        app._active_tab = MagicMock(return_value="codex")
        app._load_codex = MagicMock()
        event = self._make_event("filter-input", "python")
        app.on_input_changed(event)
        app._load_codex.assert_called_once()

    def test_input_changed_filter_input_apps_tab(self):
        """on_input_changed: filter-input on apps tab → calls _load_apps."""
        app = self._make_app()
        app._active_tab = MagicMock(return_value="apps")
        app._load_apps = MagicMock()
        event = self._make_event("filter-input", "claude")
        app.on_input_changed(event)
        app._load_apps.assert_called_once()

    def test_input_changed_other_input_id_ignored(self):
        """on_input_changed: non-filter input id → no effect."""
        app = self._make_app()
        app._load_projects = MagicMock()
        event = self._make_event("other-input", "value")
        app.on_input_changed(event)
        app._load_projects.assert_not_called()

    def test_input_changed_unknown_tab_uses_default(self):
        """on_input_changed: unknown tab → falls back to _load_projects."""
        app = self._make_app()
        app._active_tab = MagicMock(return_value="unknown")
        app._load_projects = MagicMock()
        event = self._make_event("filter-input", "test")
        app.on_input_changed(event)
        app._load_projects.assert_called_once()


@unittest.skipUnless(HAS_TEXTUAL, "textual not installed")
class TestBackgroundScanProgress(unittest.TestCase):
    """Test _background_scan progress callback lines 735-738."""

    def _make_app(self):
        with patch("nexus.tui.app.detect_clis", return_value=[]):
            return NexusApp()

    def test_background_scan_progress_callback_calls_set_subtitle(self):
        """_background_scan: progress callback calls call_from_thread (lines 735-738)."""
        app = self._make_app()
        app._scan_cancelled.clear()  # not cancelled
        app.call_from_thread = MagicMock()
        app._set_subtitle = MagicMock()

        captured_progress = []

        def fake_scan_all(on_progress=None, cancelled=None):
            if on_progress:
                captured_progress.append(on_progress)
                on_progress(1, 5, "TestProject")
            return {}

        with patch("nexus.tui.app.scan_all", side_effect=fake_scan_all), \
             patch("nexus.tui.app._update_ideas_in_data_json"), \
             patch("nexus.tui.app._update_codex_in_data_json"), \
             patch("nexus.tui.app._tui_sync"), \
             patch("nexus.tui.app._tui_sync_background"):
            # Call _background_scan directly (simulating what the daemon thread does)
            app._background_scan()

        # progress was captured and called
        self.assertEqual(len(captured_progress), 1)
        # call_from_thread was called with _set_subtitle
        app.call_from_thread.assert_called()

    def test_background_scan_cancelled_before_start(self):
        """_background_scan: scan_cancelled is set → returns early (line 731-732)."""
        app = self._make_app()
        app._scan_cancelled.set()  # cancelled before start

        scan_was_called = []

        def fake_scan_all(*args, **kwargs):
            scan_was_called.append(True)
            return {}

        with patch("nexus.tui.app.scan_all", side_effect=fake_scan_all):
            app._background_scan()

        # scan_all should NOT have been called
        self.assertEqual(len(scan_was_called), 0)

    def test_background_scan_cancelled_after_scan(self):
        """_background_scan: cancelled after scan → skips ideas update (line 742)."""
        app = self._make_app()
        app._scan_cancelled.clear()

        scan_ran = [False]
        ideas_ran = [False]

        def fake_scan_all(on_progress=None, cancelled=None):
            scan_ran[0] = True
            # Simulate cancellation happening during scan
            app._scan_cancelled.set()
            return {}

        def fake_update_ideas():
            ideas_ran[0] = True

        with patch("nexus.tui.app.scan_all", side_effect=fake_scan_all), \
             patch("nexus.tui.app._update_ideas_in_data_json", side_effect=fake_update_ideas):
            app._background_scan()

        self.assertTrue(scan_ran[0])
        # Ideas update should be skipped because cancelled is set
        self.assertFalse(ideas_ran[0])

    def test_background_scan_cancelled_after_ideas(self):
        """_background_scan: cancelled after ideas update → skips codex (line 745)."""
        app = self._make_app()
        app._scan_cancelled.clear()

        ideas_ran = [False]
        codex_ran = [False]

        def fake_scan_all(on_progress=None, cancelled=None):
            return {}

        def fake_update_ideas():
            ideas_ran[0] = True
            app._scan_cancelled.set()  # cancel after ideas

        def fake_update_codex():
            codex_ran[0] = True

        with patch("nexus.tui.app.scan_all", side_effect=fake_scan_all), \
             patch("nexus.tui.app._update_ideas_in_data_json", side_effect=fake_update_ideas), \
             patch("nexus.tui.app._update_codex_in_data_json", side_effect=fake_update_codex):
            app._background_scan()

        self.assertTrue(ideas_ran[0])
        self.assertFalse(codex_ran[0])

    def test_background_scan_cancelled_after_codex(self):
        """_background_scan: cancelled after codex update → skips tui_sync (line 748)."""
        app = self._make_app()
        app._scan_cancelled.clear()

        sync_ran = [False]

        def fake_scan_all(on_progress=None, cancelled=None):
            return {}

        def fake_update_codex():
            app._scan_cancelled.set()  # cancel after codex

        def fake_tui_sync(action):
            sync_ran[0] = True

        with patch("nexus.tui.app.scan_all", side_effect=fake_scan_all), \
             patch("nexus.tui.app._update_ideas_in_data_json"), \
             patch("nexus.tui.app._update_codex_in_data_json", side_effect=fake_update_codex), \
             patch("nexus.tui.app._tui_sync", side_effect=fake_tui_sync):
            app._background_scan()

        self.assertFalse(sync_ran[0])

    def test_background_scan_cancelled_after_sync(self):
        """_background_scan: cancelled after tui_sync → skips reload (line 751)."""
        app = self._make_app()
        app._scan_cancelled.clear()

        reload_called = [False]

        def fake_tui_sync(action):
            app._scan_cancelled.set()  # cancel after sync

        app.call_from_thread = MagicMock(side_effect=lambda *a: reload_called.__setitem__(0, True))

        with patch("nexus.tui.app.scan_all", return_value={}), \
             patch("nexus.tui.app._update_ideas_in_data_json"), \
             patch("nexus.tui.app._update_codex_in_data_json"), \
             patch("nexus.tui.app._tui_sync", side_effect=fake_tui_sync):
            app._background_scan()

        # call_from_thread (for reload) should NOT have been called
        self.assertFalse(reload_called[0])

    def test_background_scan_progress_exception_is_caught(self):
        """_background_scan: call_from_thread raises → caught by except (lines 737-738)."""
        app = self._make_app()
        app._scan_cancelled.clear()
        app.call_from_thread = MagicMock(side_effect=RuntimeError("App exited"))

        def fake_scan_all(on_progress=None, cancelled=None):
            if on_progress:
                # This should raise RuntimeError internally but be caught
                on_progress(1, 1, "TestProject")
            app._scan_cancelled.set()  # cancel after scan to simplify
            return {}

        with patch("nexus.tui.app.scan_all", side_effect=fake_scan_all):
            # Should not raise
            app._background_scan()
