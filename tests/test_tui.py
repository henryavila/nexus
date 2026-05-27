import unittest
from unittest.mock import MagicMock, patch

try:
    from nexus.cli_registry import CLI_REGISTRY, CliEntry, detect_clis
    from nexus.tui import (
        CliSelectScreen,
        CodexDetailScreen,
        EnvDetailScreen,
        IdeaDetailScreen,
        NexusApp,
    )
    from textual.widgets.data_table import RowKey
    HAS_TEXTUAL = True
except ImportError:
    HAS_TEXTUAL = False


@unittest.skipUnless(HAS_TEXTUAL, "textual not installed")
class TestTuiImport(unittest.TestCase):
    def test_can_import_tui(self):
        self.assertIsNotNone(NexusApp)

    @patch("nexus.tui.app.detect_clis", return_value=[CliEntry("claude", "claude", "Claude Code")])
    def test_app_has_required_methods(self, _mock_detect):
        app = NexusApp()
        self.assertTrue(hasattr(app, "compose"))
        self.assertTrue(hasattr(app, "action_launch_project"))

    def test_enter_binding_exists_without_priority(self):
        enter_binding = next((b for b in NexusApp.BINDINGS if b.key == "enter"), None)
        self.assertIsNotNone(enter_binding)
        self.assertFalse(enter_binding.priority)
        self.assertEqual(enter_binding.action, "launch_project")

    @patch("nexus.tui.app.detect_clis", return_value=[CliEntry("claude", "claude", "Claude Code")])
    def test_on_mount_loads_data_and_starts_scan(self, _mock_detect):
        app = NexusApp()
        fake_list = MagicMock()
        with patch.object(app, "_load_projects") as mocked_load, \
             patch.object(app, "_load_ideas"), \
             patch.object(app, "_load_codex"), \
             patch.object(app, "_load_apps"), \
             patch.object(app, "_load_environments"), \
             patch.object(app, "query_one", return_value=fake_list), \
             patch("nexus.tui.app.threading") as mock_threading:
            mock_thread = MagicMock()
            mock_threading.Thread.return_value = mock_thread
            mock_threading.Event = __import__("threading").Event
            app.on_mount()

        mocked_load.assert_called_once()
        fake_list.focus.assert_called_once()
        mock_thread.start.assert_called_once()

    def test_add_binding_label_is_generic(self):
        """The 'a' binding label should be generic since it works for Ideas and Codex tabs."""
        bindings = [b for b in NexusApp.BINDINGS if hasattr(b, 'key') and b.key == "a"]
        self.assertEqual(len(bindings), 1)
        self.assertNotIn("Idea", bindings[0].description)


@unittest.skipUnless(HAS_TEXTUAL, "textual not installed")
class TestCliRegistry(unittest.TestCase):
    def test_cli_registry_structure(self):
        self.assertTrue(len(CLI_REGISTRY) > 0)
        for cli in CLI_REGISTRY:
            self.assertIsInstance(cli, CliEntry)
            self.assertTrue(cli.name)
            self.assertTrue(cli.cmd)
            self.assertTrue(cli.label)

    @patch("nexus.cli_registry.shutil.which", return_value="/usr/bin/fake")
    def test_cli_registry_first_is_default(self, _mock_which):
        available = detect_clis()
        self.assertEqual(available[0], CLI_REGISTRY[0])

    @patch("nexus.cli_registry.shutil.which")
    def test_detect_clis_filters_by_which(self, mock_which):
        def side_effect(cmd):
            return "/usr/bin/claude" if cmd == "claude" else None
        mock_which.side_effect = side_effect
        available = detect_clis()
        self.assertEqual(len(available), 1)
        self.assertEqual(available[0].cmd, "claude")

    @patch("nexus.cli_registry.shutil.which", return_value="/usr/bin/fake")
    def test_detect_clis_preserves_order(self, _mock_which):
        available = detect_clis()
        self.assertEqual(available, list(CLI_REGISTRY))

    @patch("nexus.cli_registry.shutil.which", return_value=None)
    def test_detect_clis_none_available(self, _mock_which):
        available = detect_clis()
        self.assertEqual(available, [])


@unittest.skipUnless(HAS_TEXTUAL, "textual not installed")
class TestActionLaunchProject(unittest.TestCase):
    @patch("nexus.tui.app.detect_clis", return_value=[])
    def test_action_launch_project_no_clis(self, _mock_detect):
        app = NexusApp()
        app._active_tab = MagicMock(return_value="projects")
        app._get_selected_project = MagicMock(return_value={"path": "/tmp/test", "name": "test"})
        app.notify = MagicMock()
        app.exit = MagicMock()
        with patch("nexus.tui.app.resolve_project_path", return_value="/tmp/test"):
            with patch("nexus.tui.app.Path") as mock_path:
                mock_path.return_value.exists.return_value = True
                app.action_launch_project()
        app.notify.assert_called_once()
        self.assertIn("error", str(app.notify.call_args))
        app.exit.assert_not_called()

    @patch("nexus.tui.app.detect_clis", return_value=[CliEntry("claude", "claude", "Claude Code")])
    def test_action_launch_project_single_cli(self, _mock_detect):
        app = NexusApp()
        app._active_tab = MagicMock(return_value="projects")
        app._get_selected_project = MagicMock(return_value={"path": "/tmp/test", "name": "test"})
        app.exit = MagicMock()
        with patch("nexus.tui.app.resolve_project_path", return_value="/tmp/test"):
            with patch("nexus.tui.app.Path") as mock_path:
                mock_path.return_value.exists.return_value = True
                app.action_launch_project()
        app.exit.assert_called_once()
        result = app.exit.call_args[1]["result"]
        self.assertEqual(result[0], "launch")
        self.assertEqual(result[1]["path"], "/tmp/test")
        self.assertEqual(result[1]["cli"], "claude")

    @patch("nexus.tui.app.detect_clis", return_value=[
        CliEntry("claude", "claude", "Claude Code"),
        CliEntry("codex", "codex", "Codex CLI"),
    ])
    def test_action_launch_project_multi_cli_shows_modal(self, _mock_detect):
        """With 2+ CLIs, push_screen should be called exactly once."""
        app = NexusApp()
        app._active_tab = MagicMock(return_value="projects")
        app._get_selected_project = MagicMock(return_value={"path": "/tmp/test"})
        app.push_screen = MagicMock()
        with patch("nexus.tui.app.resolve_project_path", return_value="/tmp/test"):
            with patch("nexus.tui.app.Path") as mock_path:
                mock_path.return_value.exists.return_value = True
                app.action_launch_project()
        app.push_screen.assert_called_once()

    @patch("nexus.tui.app.detect_clis", return_value=[
        CliEntry("claude", "claude", "Claude Code"),
        CliEntry("codex", "codex", "Codex CLI"),
    ])
    def test_action_launch_project_blocked_while_modal_open(self, _mock_detect):
        """Calling action_launch_project again while modal is open must be a no-op."""
        app = NexusApp()
        app._active_tab = MagicMock(return_value="projects")
        app._get_selected_project = MagicMock(return_value={"path": "/tmp/test"})
        app.push_screen = MagicMock()
        with patch("nexus.tui.app.resolve_project_path", return_value="/tmp/test"):
            with patch("nexus.tui.app.Path") as mock_path:
                mock_path.return_value.exists.return_value = True
                app.action_launch_project()  # first call: shows modal
                app.action_launch_project()  # second call: must be no-op
        self.assertEqual(app.push_screen.call_count, 1)

    @patch("nexus.tui.app.detect_clis", return_value=[
        CliEntry("claude", "claude", "Claude Code"),
        CliEntry("codex", "codex", "Codex CLI"),
    ])
    def test_on_cli_selected_exits_with_result(self, _mock_detect):
        """Selecting a CLI should exit with launch result."""
        app = NexusApp()
        app.exit = MagicMock()
        cli = CliEntry("codex", "codex", "Codex CLI")
        app._on_cli_selected(cli, "/tmp/test")
        app.exit.assert_called_once()
        result = app.exit.call_args[1]["result"]
        self.assertEqual(result, ("launch", {"path": "/tmp/test", "cli": "codex"}))

    @patch("nexus.tui.app.detect_clis", return_value=[
        CliEntry("claude", "claude", "Claude Code"),
        CliEntry("codex", "codex", "Codex CLI"),
    ])
    def test_on_cli_selected_cancel_does_not_exit(self, _mock_detect):
        """Cancelling the modal (None) should not exit the app."""
        app = NexusApp()
        app.exit = MagicMock()
        app._on_cli_selected(None, "/tmp/test")
        app.exit.assert_not_called()

    @patch("nexus.tui.app.detect_clis", return_value=[
        CliEntry("claude", "claude", "Claude Code"),
        CliEntry("codex", "codex", "Codex CLI"),
    ])
    def test_on_cli_selected_resets_modal_guard(self, _mock_detect):
        """After selection, the modal guard must reset so Enter works again later."""
        app = NexusApp()
        app._active_tab = MagicMock(return_value="projects")
        app._get_selected_project = MagicMock(return_value={"path": "/tmp/test"})
        app.push_screen = MagicMock()
        app.exit = MagicMock()
        with patch("nexus.tui.app.resolve_project_path", return_value="/tmp/test"):
            with patch("nexus.tui.app.Path") as mock_path:
                mock_path.return_value.exists.return_value = True
                app.action_launch_project()  # opens modal, sets guard
        self.assertTrue(app._cli_modal_open)
        # Simulate selection callback
        app._on_cli_selected(CliEntry("claude", "claude", "Claude Code"), "/tmp/test")
        self.assertFalse(app._cli_modal_open)

    @patch("nexus.tui.app.detect_clis", return_value=[
        CliEntry("claude", "claude", "Claude Code"),
        CliEntry("codex", "codex", "Codex CLI"),
    ])
    def test_on_cli_selected_cancel_resets_modal_guard(self, _mock_detect):
        """After cancel (Escape), the modal guard must reset."""
        app = NexusApp()
        app._active_tab = MagicMock(return_value="projects")
        app._get_selected_project = MagicMock(return_value={"path": "/tmp/test"})
        app.push_screen = MagicMock()
        with patch("nexus.tui.app.resolve_project_path", return_value="/tmp/test"):
            with patch("nexus.tui.app.Path") as mock_path:
                mock_path.return_value.exists.return_value = True
                app.action_launch_project()  # opens modal, sets guard
        self.assertTrue(app._cli_modal_open)
        # Simulate cancel callback
        app._on_cli_selected(None, "/tmp/test")
        self.assertFalse(app._cli_modal_open)


@unittest.skipUnless(HAS_TEXTUAL, "textual not installed")
class TestCliSelectScreen(unittest.TestCase):
    def test_cli_select_screen_instantiation(self):
        clis = [CliEntry("claude", "claude", "Claude Code"), CliEntry("codex", "codex", "Codex CLI")]
        screen = CliSelectScreen(clis)
        self.assertEqual(screen.clis, clis)
        self.assertEqual(len(screen.clis), 2)




@unittest.skipUnless(HAS_TEXTUAL, "textual not installed")
class TestCliModalEnterFix(unittest.TestCase):
    """Enter in the CLI modal must work — not be consumed by App's priority binding."""

    def test_app_enter_binding_not_priority(self):
        """Enter binding must NOT have priority=True (it bypasses ModalScreen barrier,
        preventing OptionList from receiving Enter in the CLI selection modal)."""
        enter_binding = next((b for b in NexusApp.BINDINGS if b.key == "enter"), None)
        self.assertIsNotNone(enter_binding)
        self.assertFalse(
            enter_binding.priority,
            "Enter binding must not use priority=True — it blocks ModalScreen widgets"
        )

    @patch("nexus.tui.app.detect_clis", return_value=[CliEntry("claude", "claude", "Claude Code")])
    def test_on_data_table_row_selected_calls_launch_for_project(self, _mock_detect):
        """DataTable.RowSelected on a project row must delegate to action_launch_project."""
        app = NexusApp()
        app._is_mounted = True
        app._group_keys = set()
        app.action_launch_project = MagicMock()

        event = MagicMock()
        event.row_key = RowKey("nexus")

        app.on_data_table_row_selected(event)
        app.action_launch_project.assert_called_once()

    @patch("nexus.tui.app.detect_clis", return_value=[CliEntry("claude", "claude", "Claude Code")])
    def test_on_data_table_row_selected_ignores_group_header(self, _mock_detect):
        """DataTable.RowSelected on a group header row must not delegate to action_launch_project."""
        app = NexusApp()
        app._is_mounted = True
        app._group_keys = {RowKey("_group:tech")}
        app.action_launch_project = MagicMock()

        event = MagicMock()
        event.row_key = RowKey("_group:tech")

        app.on_data_table_row_selected(event)
        app.action_launch_project.assert_not_called()


@unittest.skipUnless(HAS_TEXTUAL, "textual not installed")
class TestCliModalEnterIntegration(unittest.IsolatedAsyncioTestCase):
    """Integration: verify CliSelectScreen Enter selection works end-to-end."""

    async def test_enter_selects_highlighted_cli(self):
        """Pressing Enter in CliSelectScreen must dismiss with the highlighted CLI."""
        from textual.app import App as BaseApp, ComposeResult
        from textual.widgets import Static

        clis = [CliEntry("claude", "claude", "Claude Code"), CliEntry("codex", "codex", "Codex CLI")]
        selected = []

        class HostApp(BaseApp):
            def compose(self) -> ComposeResult:
                yield Static("host")

            def on_mount(self) -> None:
                self.push_screen(
                    CliSelectScreen(clis),
                    callback=lambda cli: selected.append(cli) if cli is not None else None,
                )

        async with HostApp().run_test() as pilot:
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()

        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0], clis[0])


@unittest.skipUnless(HAS_TEXTUAL, "textual not installed")
class TestNumberKeyTabSwitchIntegration(unittest.IsolatedAsyncioTestCase):
    """Integration: pressing digit keys switches tabs in a running app."""

    async def test_press_2_switches_to_projects(self):
        """Pressing '2' should activate the projects tab."""
        from textual.widgets import TabbedContent
        with patch("nexus.tui.app.detect_clis", return_value=[CliEntry("claude", "claude", "Claude Code")]):
            with patch("nexus.tui.app.scan_all"):
                with patch("nexus.tui.app._update_ideas_in_data_json"):
                    with patch("nexus.tui.app._update_codex_in_data_json"):
                        app = NexusApp()
                        async with app.run_test() as pilot:
                            await pilot.pause()
                            tabs = app.query_one("#tabs", TabbedContent)
                            self.assertEqual(tabs.active, "ideas")
                            await pilot.press("2")
                            await pilot.pause()
                            self.assertEqual(tabs.active, "projects")

    async def test_press_1_stays_on_ideas(self):
        """Pressing '1' when already on ideas should be a no-op (no crash)."""
        from textual.widgets import TabbedContent
        with patch("nexus.tui.app.detect_clis", return_value=[CliEntry("claude", "claude", "Claude Code")]):
            with patch("nexus.tui.app.scan_all"):
                with patch("nexus.tui.app._update_ideas_in_data_json"):
                    with patch("nexus.tui.app._update_codex_in_data_json"):
                        app = NexusApp()
                        async with app.run_test() as pilot:
                            await pilot.pause()
                            tabs = app.query_one("#tabs", TabbedContent)
                            await pilot.press("1")
                            await pilot.pause()
                            self.assertEqual(tabs.active, "ideas")


@unittest.skipUnless(HAS_TEXTUAL, "textual not installed")
class TestNumberKeyTabSwitch(unittest.TestCase):
    """Number keys (1, 2, ...) should switch tabs instantly."""

    def test_tab_order_registry_exists(self):
        """NexusApp must have a TAB_ORDER list of (pane_id, label) tuples."""
        self.assertTrue(hasattr(NexusApp, "TAB_ORDER"))
        self.assertIsInstance(NexusApp.TAB_ORDER, list)
        self.assertEqual(NexusApp.TAB_ORDER[0][0], "ideas")
        self.assertEqual(NexusApp.TAB_ORDER[1][0], "projects")
        self.assertEqual(NexusApp.TAB_ORDER[4][0], "codex")

    def test_number_bindings_match_tab_order(self):
        """There must be a Binding for each digit 1..len(TAB_ORDER)."""
        for i in range(len(NexusApp.TAB_ORDER)):
            digit = str(i + 1)
            binding = next(
                (b for b in NexusApp.BINDINGS if b.key == digit), None
            )
            self.assertIsNotNone(binding, f"Missing binding for key '{digit}'")
            self.assertEqual(binding.action, f"switch_tab({i})")

    @patch("nexus.tui.app.detect_clis", return_value=[CliEntry("claude", "claude", "Claude Code")])
    def test_action_switch_tab_activates_correct_pane(self, _mock_detect):
        """action_switch_tab(index) should set TabbedContent.active to the correct pane ID."""
        app = NexusApp()
        fake_tabs = MagicMock()
        fake_tabs.active = "ideas"
        with patch.object(app, "query_one", return_value=fake_tabs):
            app.action_switch_tab(1)
        self.assertEqual(fake_tabs.active, "projects")

    @patch("nexus.tui.app.detect_clis", return_value=[CliEntry("claude", "claude", "Claude Code")])
    def test_action_switch_tab_out_of_range_is_noop(self, _mock_detect):
        """Out-of-range index should not crash."""
        app = NexusApp()
        app.notify = MagicMock()
        try:
            fake_tabs = MagicMock()
            with patch.object(app, "query_one", return_value=fake_tabs):
                app.action_switch_tab(99)
        except Exception:
            self.fail("action_switch_tab raised on out-of-range index")


@unittest.skipUnless(HAS_TEXTUAL, "textual not installed")
class TestIdeaDetailScreen(unittest.TestCase):
    """IdeaDetailScreen modal for read-only idea details."""

    def test_idea_detail_screen_exists(self):
        """IdeaDetailScreen can be imported and is a subclass of ModalScreen."""
        from textual.screen import ModalScreen
        self.assertTrue(issubclass(IdeaDetailScreen, ModalScreen))

    def test_idea_detail_shows_all_fields(self):
        """IdeaDetailScreen stores the idea dict in idea_data."""
        idea = {
            "id": "abc12345",
            "title": "Test Idea",
            "description": "A great idea",
            "priority": "high",
            "domain": "pessoal",
            "tags": ["ai", "tools"],
            "references": ["https://example.com"],
            "notes": "Some notes",
            "created": "2026-03-01",
        }
        screen = IdeaDetailScreen(idea)
        self.assertEqual(screen.idea_data, idea)
        self.assertEqual(screen.idea_data["title"], "Test Idea")
        self.assertEqual(screen.idea_data["priority"], "high")
        self.assertEqual(screen.idea_data["tags"], ["ai", "tools"])

    def test_enter_on_idea_shows_detail(self):
        """action_launch_project on ideas tab calls push_screen with IdeaDetailScreen."""
        app = NexusApp.__new__(NexusApp)
        app._cli_modal_open = False

        with patch.object(app, '_active_tab', return_value='ideas'), \
             patch.object(app, '_get_selected_idea', return_value={
                 "id": "abc12345", "title": "Test", "description": "Desc",
                 "priority": "high", "domain": "pessoal",
             }), \
             patch.object(app, 'push_screen') as mock_push:
            app.action_launch_project()
            mock_push.assert_called_once()
            args = mock_push.call_args
            self.assertIsInstance(args[0][0], IdeaDetailScreen)

    @patch("nexus.tui.app.detect_clis", return_value=[CliEntry("claude", "claude", "Claude Code")])
    def test_on_data_table_row_selected_handles_idea_row(self, _mock_detect):
        """DataTable.RowSelected on an idea row must delegate to action_launch_project."""
        app = NexusApp()
        app._is_mounted = True
        app._group_keys = set()
        app.action_launch_project = MagicMock()

        event = MagicMock()
        event.row_key = RowKey("abc12345")

        app.on_data_table_row_selected(event)
        app.action_launch_project.assert_called_once()

    def test_idea_detail_dismiss_returns_edit(self):
        """action_edit_idea should dismiss with 'edit' string."""
        idea = {"id": "abc12345", "title": "Test", "priority": "medium"}
        screen = IdeaDetailScreen(idea)
        screen.dismiss = MagicMock()
        screen.action_edit_idea()
        screen.dismiss.assert_called_once_with("edit")

    def test_idea_detail_dismiss_returns_none(self):
        """action_dismiss_screen should dismiss with None."""
        idea = {"id": "abc12345", "title": "Test", "priority": "medium"}
        screen = IdeaDetailScreen(idea)
        screen.dismiss = MagicMock()
        screen.action_dismiss_screen()
        screen.dismiss.assert_called_once_with(None)


@unittest.skipUnless(HAS_TEXTUAL, "textual not installed")
class TestCodexDetailScreen(unittest.TestCase):
    """CodexDetailScreen modal for rendered markdown content."""

    def test_codex_detail_screen_exists(self):
        from textual.screen import ModalScreen
        self.assertTrue(issubclass(CodexDetailScreen, ModalScreen))

    def test_codex_detail_stores_data(self):
        entry = {
            "slug": "my-guide",
            "title": "My Guide",
            "domain": "ferramentas",
            "tags": ["bmad"],
            "content": "## Section\n\nContent here.",
        }
        screen = CodexDetailScreen(entry)
        self.assertEqual(screen.codex_data, entry)
        self.assertEqual(screen.codex_data["title"], "My Guide")

    def test_codex_detail_dismiss_returns_edit(self):
        entry = {"slug": "test", "title": "Test"}
        screen = CodexDetailScreen(entry)
        screen.dismiss = MagicMock()
        screen.action_edit_codex()
        screen.dismiss.assert_called_once_with("edit")

    def test_codex_detail_dismiss_returns_none(self):
        entry = {"slug": "test", "title": "Test"}
        screen = CodexDetailScreen(entry)
        screen.dismiss = MagicMock()
        screen.action_dismiss_screen()
        screen.dismiss.assert_called_once_with(None)


@unittest.skipUnless(HAS_TEXTUAL, "textual not installed")
class TestCodexTuiActions(unittest.TestCase):
    """Codex tab actions in NexusApp."""

    def test_enter_on_codex_shows_detail(self):
        app = NexusApp.__new__(NexusApp)
        app._cli_modal_open = False

        with patch.object(app, '_active_tab', return_value='codex'), \
             patch.object(app, '_get_selected_codex', return_value={
                 "slug": "test", "title": "Test", "domain": "pessoal",
                 "content": "Hello",
             }), \
             patch.object(app, 'push_screen') as mock_push:
            app.action_launch_project()
            mock_push.assert_called_once()
            args = mock_push.call_args
            self.assertIsInstance(args[0][0], CodexDetailScreen)

    def test_edit_on_codex_tab_exits_with_slug(self):
        app = NexusApp.__new__(NexusApp)
        app.exit = MagicMock()

        with patch.object(app, '_active_tab', return_value='codex'), \
             patch.object(app, '_get_selected_codex', return_value={
                 "slug": "my-guide", "title": "My Guide",
             }):
            app.action_edit_item()
            app.exit.assert_called_once()
            result = app.exit.call_args[1]["result"]
            self.assertEqual(result, ("codex_edit", "my-guide"))

    def test_remove_on_codex_tab_exits_with_slug(self):
        app = NexusApp.__new__(NexusApp)
        app.exit = MagicMock()

        with patch.object(app, '_active_tab', return_value='codex'), \
             patch.object(app, '_get_selected_codex', return_value={
                 "slug": "to-remove", "title": "Remove Me",
             }):
            app.action_remove_item()
            app.exit.assert_called_once()
            result = app.exit.call_args[1]["result"]
            self.assertEqual(result, ("codex_remove", "to-remove"))

    def test_add_on_codex_tab_exits_with_codex_add(self):
        app = NexusApp.__new__(NexusApp)
        app.exit = MagicMock()

        with patch.object(app, '_active_tab', return_value='codex'):
            app.action_add_idea()
            app.exit.assert_called_once()
            result = app.exit.call_args[1]["result"]
            self.assertEqual(result, ("codex_add", None))

    @patch("nexus.tui.app.detect_clis", return_value=[CliEntry("claude", "claude", "Claude Code")])
    def test_on_data_table_row_selected_handles_codex_row(self, _mock_detect):
        app = NexusApp()
        app._group_keys = set()
        app.action_launch_project = MagicMock()

        event = MagicMock()
        event.row_key = RowKey("codex:my-entry")

        app.on_data_table_row_selected(event)
        app.action_launch_project.assert_called_once()

    def test_codex_detail_dismissed_edit_exits(self):
        app = NexusApp.__new__(NexusApp)
        app.exit = MagicMock()

        with patch.object(app, '_get_selected_codex', return_value={
            "slug": "my-guide", "title": "My Guide",
        }):
            app._on_codex_detail_dismissed("edit")
            app.exit.assert_called_once()
            result = app.exit.call_args[1]["result"]
            self.assertEqual(result, ("codex_edit", "my-guide"))

    def test_codex_detail_dismissed_none_no_exit(self):
        app = NexusApp.__new__(NexusApp)
        app.exit = MagicMock()
        app._on_codex_detail_dismissed(None)
        app.exit.assert_not_called()


@unittest.skipUnless(HAS_TEXTUAL, "textual not installed")
class TestCodexTabSwitchIntegration(unittest.IsolatedAsyncioTestCase):
    async def test_press_5_switches_to_codex(self):
        from textual.widgets import TabbedContent
        with patch("nexus.tui.app.detect_clis", return_value=[CliEntry("claude", "claude", "Claude Code")]):
            with patch("nexus.tui.app.scan_all"):
                with patch("nexus.tui.app._update_ideas_in_data_json"):
                    with patch("nexus.tui.app._update_codex_in_data_json"):
                        app = NexusApp()
                        async with app.run_test() as pilot:
                            await pilot.pause()
                            tabs = app.query_one("#tabs", TabbedContent)
                            self.assertEqual(tabs.active, "ideas")
                            await pilot.press("5")
                            await pilot.pause()
                            self.assertEqual(tabs.active, "codex")


@unittest.skipUnless(HAS_TEXTUAL, "textual not installed")
class TestTabActivatedGuard(unittest.TestCase):
    """on_tabbed_content_tab_activated must not crash before mount completes."""

    @patch("nexus.tui.app.detect_clis", return_value=[CliEntry("claude", "claude", "Claude Code")])
    def test_tab_activated_before_mount_is_noop(self, _mock_detect):
        """TabActivated firing before on_mount should not raise MountError."""
        from textual.widgets import TabbedContent
        app = NexusApp()
        # Simulate TabActivated event before app is mounted
        event = MagicMock()
        event.pane = MagicMock()
        event.pane.id = "ideas"
        # _is_mounted should be False before on_mount runs
        try:
            app.on_tabbed_content_tab_activated(event)
        except Exception:
            self.fail("on_tabbed_content_tab_activated raised before mount")


@unittest.skipUnless(HAS_TEXTUAL, "textual not installed")
class TestNewTabs(unittest.TestCase):
    """Tests for the 5-tab TUI layout (Apps, Environments)."""

    def test_tab_order_has_five_tabs(self):
        self.assertEqual(len(NexusApp.TAB_ORDER), 5)

    def test_tab_names(self):
        tab_ids = [t[0] for t in NexusApp.TAB_ORDER]
        self.assertIn("apps", tab_ids)
        self.assertIn("environments", tab_ids)

    def test_tab_order_sequence(self):
        tab_ids = [t[0] for t in NexusApp.TAB_ORDER]
        self.assertEqual(tab_ids, ["ideas", "projects", "apps", "environments", "codex"])

    def test_number_bindings_for_all_five_tabs(self):
        for i in range(5):
            digit = str(i + 1)
            binding = next((b for b in NexusApp.BINDINGS if b.key == digit), None)
            self.assertIsNotNone(binding, f"Missing binding for key '{digit}'")
            self.assertEqual(binding.action, f"switch_tab({i})")


@unittest.skipUnless(HAS_TEXTUAL, "textual not installed")
class TestAppRowData(unittest.TestCase):
    """Apps are now rendered via DataTable; verify _app_row_data storage works."""

    @patch("nexus.tui.app.detect_clis", return_value=[])
    def test_app_row_data_stores_dict(self, _detect):
        """NexusApp._app_row_data should be a dict that maps RowKey → app dict."""
        app = NexusApp()
        # Simulate what _load_apps does
        app._app_row_data[RowKey("test-app")] = {"name": "Test App", "slug": "test-app"}
        self.assertEqual(app._app_row_data[RowKey("test-app")]["slug"], "test-app")


@unittest.skipUnless(HAS_TEXTUAL, "textual not installed")
class TestEnvRowData(unittest.TestCase):
    """Environments are now rendered via DataTable; verify _env_row_data storage works."""

    @patch("nexus.tui.app.detect_clis", return_value=[])
    def test_env_row_data_stores_dict(self, _detect):
        """NexusApp._env_row_data should be a dict that maps RowKey -> env dict."""
        app = NexusApp()
        env_data = {"hostname": "mypc", "name": "Home PC", "location": "casa", "last_seen": "2026-03-10"}
        app._env_row_data[RowKey("env:mypc")] = env_data
        self.assertEqual(app._env_row_data[RowKey("env:mypc")]["hostname"], "mypc")


@unittest.skipUnless(HAS_TEXTUAL, "textual not installed")
class TestEnvDetailScreen(unittest.TestCase):
    """EnvDetailScreen modal."""

    def test_env_detail_screen_exists(self):
        from textual.screen import ModalScreen
        self.assertTrue(issubclass(EnvDetailScreen, ModalScreen))

    def test_env_detail_stores_data(self):
        env = {"hostname": "mypc", "name": "Home PC", "location": "casa", "last_seen": "2026-03-10"}
        screen = EnvDetailScreen(env)
        self.assertEqual(screen.env_data, env)

    def test_env_detail_dismiss_returns_none(self):
        env = {"hostname": "mypc", "name": "Home PC"}
        screen = EnvDetailScreen(env)
        screen.dismiss = MagicMock()
        screen.action_dismiss_screen()
        screen.dismiss.assert_called_once_with(None)


@unittest.skipUnless(HAS_TEXTUAL, "textual not installed")
class TestNewTabActions(unittest.TestCase):
    """Actions for apps, environments tabs."""

    def test_enter_on_apps_shows_detail_or_opens_web(self):
        """action_launch_project on apps tab with URL opens web."""
        app = NexusApp.__new__(NexusApp)
        app._cli_modal_open = False

        with patch.object(app, '_active_tab', return_value='apps'), \
             patch.object(app, '_get_selected_app', return_value={
                 "slug": "test-app", "name": "Test App", "url": "https://example.com",
             }), \
             patch('webbrowser.open') as mock_open, \
             patch.object(app, 'notify'):
            app.action_launch_project()
            mock_open.assert_called_once_with("https://example.com")

    def test_enter_on_environments_shows_detail(self):
        """action_launch_project on environments tab shows EnvDetailScreen."""
        app = NexusApp.__new__(NexusApp)
        app._cli_modal_open = False

        with patch.object(app, '_active_tab', return_value='environments'), \
             patch.object(app, '_get_selected_env', return_value={
                 "hostname": "mypc", "name": "Home PC", "location": "casa",
             }), \
             patch.object(app, 'push_screen') as mock_push:
            app.action_launch_project()
            mock_push.assert_called_once()
            args = mock_push.call_args
            self.assertIsInstance(args[0][0], EnvDetailScreen)

    def test_edit_on_apps_tab(self):
        app = NexusApp.__new__(NexusApp)
        app.exit = MagicMock()

        with patch.object(app, '_active_tab', return_value='apps'), \
             patch.object(app, '_get_selected_app', return_value={
                 "slug": "my-app", "name": "My App",
             }):
            app.action_edit_item()
            app.exit.assert_called_once()
            result = app.exit.call_args[1]["result"]
            self.assertEqual(result, ("app_edit", "my-app"))

    def test_remove_on_apps_tab(self):
        app = NexusApp.__new__(NexusApp)
        app.exit = MagicMock()

        with patch.object(app, '_active_tab', return_value='apps'), \
             patch.object(app, '_get_selected_app', return_value={
                 "slug": "my-app", "name": "My App",
             }):
            app.action_remove_item()
            app.exit.assert_called_once()
            result = app.exit.call_args[1]["result"]
            self.assertEqual(result, ("app_remove", "my-app"))

    def test_add_on_apps_tab(self):
        app = NexusApp.__new__(NexusApp)
        app.exit = MagicMock()

        with patch.object(app, '_active_tab', return_value='apps'):
            app.action_add_idea()
            app.exit.assert_called_once()
            result = app.exit.call_args[1]["result"]
            self.assertEqual(result, ("app_add", None))

    def test_note_on_apps_tab(self):
        app = NexusApp.__new__(NexusApp)
        app.exit = MagicMock()

        with patch.object(app, '_active_tab', return_value='apps'), \
             patch.object(app, '_get_selected_app', return_value={
                 "slug": "my-app", "name": "My App",
             }):
            app.action_add_note()
            app.exit.assert_called_once()
            result = app.exit.call_args[1]["result"]
            self.assertEqual(result, ("app_note", "my-app"))

    def test_promote_on_projects_tab_warns(self):
        """p key on projects tab should show warning (promote removed)."""
        app = NexusApp.__new__(NexusApp)
        app.exit = MagicMock()
        app.notify = MagicMock()

        with patch.object(app, '_active_tab', return_value='projects'):
            app.action_promote_idea()
            app.exit.assert_not_called()
            app.notify.assert_called_once()

    def test_on_data_table_row_selected_handles_app_row(self):
        """DataTable.RowSelected on an app row must delegate to action_launch_project."""
        app = NexusApp.__new__(NexusApp)
        app._cli_modal_open = False
        app._group_keys = set()
        app.action_launch_project = MagicMock()

        event = MagicMock()
        event.row_key = RowKey("test-app")

        app.on_data_table_row_selected(event)
        app.action_launch_project.assert_called_once()

    def test_on_data_table_row_selected_handles_env_row(self):
        app = NexusApp.__new__(NexusApp)
        app._cli_modal_open = False
        app._group_keys = set()
        app.action_launch_project = MagicMock()

        event = MagicMock()
        event.row_key = RowKey("env:mypc")

        app.on_data_table_row_selected(event)
        app.action_launch_project.assert_called_once()


@unittest.skipUnless(HAS_TEXTUAL, "textual not installed")
class TestNewTabSwitchIntegration(unittest.IsolatedAsyncioTestCase):
    """Integration: pressing digit keys switches to new tabs."""

    async def test_press_3_switches_to_apps(self):
        from textual.widgets import TabbedContent
        with patch("nexus.tui.app.detect_clis", return_value=[CliEntry("claude", "claude", "Claude Code")]):
            with patch("nexus.tui.app.scan_all"):
                with patch("nexus.tui.app._update_ideas_in_data_json"):
                    with patch("nexus.tui.app._update_codex_in_data_json"):
                        app = NexusApp()
                        async with app.run_test() as pilot:
                            await pilot.pause()
                            tabs = app.query_one("#tabs", TabbedContent)
                            self.assertEqual(tabs.active, "ideas")
                            await pilot.press("3")
                            await pilot.pause()
                            self.assertEqual(tabs.active, "apps")

    async def test_press_5_switches_to_codex(self):
        from textual.widgets import TabbedContent
        with patch("nexus.tui.app.detect_clis", return_value=[CliEntry("claude", "claude", "Claude Code")]):
            with patch("nexus.tui.app.scan_all"):
                with patch("nexus.tui.app._update_ideas_in_data_json"):
                    with patch("nexus.tui.app._update_codex_in_data_json"):
                        app = NexusApp()
                        async with app.run_test() as pilot:
                            await pilot.pause()
                            tabs = app.query_one("#tabs", TabbedContent)
                            await pilot.press("5")
                            await pilot.pause()
                            self.assertEqual(tabs.active, "codex")


@unittest.skipUnless(HAS_TEXTUAL, "textual not installed")
class TestBackgroundScanSyncs(unittest.TestCase):
    """_background_scan() must call auto_sync_registry after scan_all() to
    avoid leaving environments.yml dirty — which causes conflicts on the
    next git pull from another PC."""

    @patch("nexus.tui.app.detect_clis", return_value=[CliEntry("claude", "claude", "Claude Code")])
    @patch("nexus.tui.app.auto_sync_registry")
    @patch("nexus.tui.app._update_codex_in_data_json")
    @patch("nexus.tui.app._update_ideas_in_data_json")
    @patch("nexus.tui.app.scan_all")
    def test_background_scan_calls_auto_sync(self, mock_scan, mock_ideas,
                                              mock_codex, mock_sync, _detect):
        app = NexusApp()
        app.call_from_thread = MagicMock()
        app._background_scan()
        mock_sync.assert_called_once()

    @patch("nexus.tui.app.detect_clis", return_value=[CliEntry("claude", "claude", "Claude Code")])
    @patch("nexus.tui.app.auto_sync_registry")
    @patch("nexus.tui.app._update_codex_in_data_json")
    @patch("nexus.tui.app._update_ideas_in_data_json")
    @patch("nexus.tui.app.scan_all")
    def test_background_scan_syncs_after_scan_not_before(self, mock_scan,
                                                          mock_ideas, mock_codex,
                                                          mock_sync, _detect):
        """auto_sync must run AFTER scan_all, not before."""
        call_order = []
        mock_scan.side_effect = lambda **kw: call_order.append("scan")
        mock_sync.side_effect = lambda *a, **kw: call_order.append("sync")

        app = NexusApp()
        app.call_from_thread = MagicMock()
        app._background_scan()
        self.assertEqual(call_order, ["scan", "sync"])

    @patch("nexus.tui.app.detect_clis", return_value=[CliEntry("claude", "claude", "Claude Code")])
    @patch("nexus.tui.app.auto_sync_registry")
    @patch("nexus.tui.app._update_codex_in_data_json")
    @patch("nexus.tui.app._update_ideas_in_data_json")
    @patch("nexus.tui.app.scan_all")
    def test_background_scan_sync_uses_scan_command(self, mock_scan, mock_ideas,
                                                     mock_codex, mock_sync, _detect):
        """Sync commit message should identify it as a scan sync."""
        app = NexusApp()
        app.call_from_thread = MagicMock()
        app._background_scan()
        args = mock_sync.call_args
        # Second argument should contain "scan"
        self.assertIn("scan", args[0][1] if len(args[0]) > 1 else args[1].get("command", ""))


@unittest.skipUnless(HAS_TEXTUAL, "textual not installed")
class TestBackgroundScanCancellation(unittest.TestCase):
    """_background_scan must check cancellation to avoid blocking app exit."""

    @patch("nexus.tui.app.detect_clis", return_value=[CliEntry("claude", "claude", "Claude Code")])
    def test_nexus_app_has_scan_cancelled_event(self, _detect):
        """NexusApp must have a _scan_cancelled threading.Event."""
        import threading
        app = NexusApp()
        self.assertTrue(hasattr(app, "_scan_cancelled"))
        self.assertIsInstance(app._scan_cancelled, threading.Event)
        self.assertFalse(app._scan_cancelled.is_set())

    @patch("nexus.tui.app.detect_clis", return_value=[CliEntry("claude", "claude", "Claude Code")])
    def test_exit_sets_scan_cancelled(self, _detect):
        """Calling exit() must set _scan_cancelled so the background thread returns."""
        app = NexusApp()
        app._close_messages_no_wait = MagicMock()
        with patch.object(type(app), "exit") as _:
            pass
        app.exit = MagicMock(wraps=app.exit)
        app.exit(result=None)
        self.assertTrue(app._scan_cancelled.is_set())

    @patch("nexus.tui.app.detect_clis", return_value=[CliEntry("claude", "claude", "Claude Code")])
    @patch("nexus.tui.app._tui_sync")
    @patch("nexus.tui.app._update_codex_in_data_json")
    @patch("nexus.tui.app._update_ideas_in_data_json")
    @patch("nexus.tui.app.scan_all")
    def test_background_scan_skips_work_when_cancelled(self, mock_scan, mock_ideas,
                                                         mock_codex, mock_sync, _detect):
        """When _scan_cancelled is set, _background_scan should return early."""
        app = NexusApp()
        app.call_from_thread = MagicMock()
        app._scan_cancelled.set()
        app._background_scan()
        mock_scan.assert_not_called()
        mock_ideas.assert_not_called()
        mock_codex.assert_not_called()
        mock_sync.assert_not_called()

    @patch("nexus.tui.app.detect_clis", return_value=[CliEntry("claude", "claude", "Claude Code")])
    @patch("nexus.tui.app._tui_sync")
    @patch("nexus.tui.app._update_codex_in_data_json")
    @patch("nexus.tui.app._update_ideas_in_data_json")
    @patch("nexus.tui.app.scan_all")
    def test_background_scan_passes_cancelled_to_scan_all(self, mock_scan, mock_ideas,
                                                            mock_codex, mock_sync, _detect):
        """_background_scan should pass a cancelled callback to scan_all."""
        app = NexusApp()
        app.call_from_thread = MagicMock()
        app._background_scan()
        mock_scan.assert_called_once()
        call_kwargs = mock_scan.call_args[1]
        self.assertIn("cancelled", call_kwargs)
        self.assertTrue(callable(call_kwargs["cancelled"]))

    @patch("nexus.tui.app.detect_clis", return_value=[CliEntry("claude", "claude", "Claude Code")])
    @patch("nexus.tui.app._tui_sync")
    @patch("nexus.tui.app._update_codex_in_data_json")
    @patch("nexus.tui.app._update_ideas_in_data_json")
    @patch("nexus.tui.app.scan_all")
    def test_background_scan_skips_sync_when_cancelled_during_scan(self, mock_scan,
                                                                      mock_ideas, mock_codex,
                                                                      mock_sync, _detect):
        """If cancelled during scan_all, subsequent steps should be skipped."""
        app = NexusApp()
        app.call_from_thread = MagicMock()

        def cancel_during_scan(**kwargs):
            app._scan_cancelled.set()

        mock_scan.side_effect = cancel_during_scan
        app._background_scan()
        mock_scan.assert_called_once()
        mock_ideas.assert_not_called()
        mock_sync.assert_not_called()


@unittest.skipUnless(HAS_TEXTUAL, "textual not installed")
class TestBackgroundScanDaemonThread(unittest.TestCase):
    """Background scan must run as a daemon thread, NOT via run_worker.

    run_worker uses asyncio's default executor. asyncio.run() calls
    loop.shutdown_default_executor() which joins ALL executor threads,
    blocking app.run() until the scan finishes. Daemon threads bypass this.
    """

    @patch("nexus.tui.app.detect_clis", return_value=[CliEntry("claude", "claude", "Claude Code")])
    def test_on_mount_does_not_use_run_worker(self, _detect):
        """on_mount must NOT use run_worker (executor threads block exit)."""
        app = NexusApp()
        fake_list = MagicMock()
        with patch.object(app, "_load_projects"), \
             patch.object(app, "_load_ideas"), \
             patch.object(app, "_load_codex"), \
             patch.object(app, "_load_apps"), \
             patch.object(app, "_load_environments"), \
             patch.object(app, "query_one", return_value=fake_list), \
             patch.object(app, "run_worker") as mock_run_worker, \
             patch("nexus.tui.app.threading") as mock_threading:
            mock_thread = MagicMock()
            mock_threading.Thread.return_value = mock_thread
            mock_threading.Event = __import__("threading").Event
            app.on_mount()
        mock_run_worker.assert_not_called()

    @patch("nexus.tui.app.detect_clis", return_value=[CliEntry("claude", "claude", "Claude Code")])
    def test_on_mount_starts_daemon_thread(self, _detect):
        """on_mount must start _background_scan in a daemon thread."""
        app = NexusApp()
        fake_list = MagicMock()
        with patch.object(app, "_load_projects"), \
             patch.object(app, "_load_ideas"), \
             patch.object(app, "_load_codex"), \
             patch.object(app, "_load_apps"), \
             patch.object(app, "_load_environments"), \
             patch.object(app, "query_one", return_value=fake_list), \
             patch("nexus.tui.app.threading") as mock_threading:
            mock_thread = MagicMock()
            mock_threading.Thread.return_value = mock_thread
            mock_threading.Event = __import__("threading").Event
            app.on_mount()
        mock_threading.Thread.assert_called_once_with(
            target=app._background_scan, daemon=True,
        )
        mock_thread.start.assert_called_once()

    @patch("nexus.tui.app.detect_clis", return_value=[CliEntry("claude", "claude", "Claude Code")])
    @patch("nexus.tui.app._tui_sync")
    @patch("nexus.tui.app._update_codex_in_data_json")
    @patch("nexus.tui.app._update_ideas_in_data_json")
    @patch("nexus.tui.app.scan_all")
    def test_background_scan_handles_call_from_thread_error(self, mock_scan,
                                                              mock_ideas, mock_codex,
                                                              mock_sync, _detect):
        """_background_scan must not crash if call_from_thread raises (app already exited)."""
        app = NexusApp()
        app.call_from_thread = MagicMock(side_effect=RuntimeError("loop closed"))
        # Should not raise
        try:
            app._background_scan()
        except RuntimeError:
            self.fail("_background_scan raised RuntimeError from call_from_thread")


@unittest.skipUnless(HAS_TEXTUAL, "textual not installed")
class TestRunTuiNonBlockingSync(unittest.TestCase):
    """_tui_sync calls in run_tui must not block the main thread."""

    @patch("nexus.tui.app._tui_sync")
    def test_tui_sync_runs_in_background_thread(self, mock_sync):
        """_tui_sync_background should run _tui_sync in a daemon thread."""
        from nexus.tui import _tui_sync_background
        with patch("nexus.tui.app.threading") as mock_threading:
            mock_thread = MagicMock()
            mock_threading.Thread.return_value = mock_thread
            _tui_sync_background("idea-promote")
        mock_threading.Thread.assert_called_once_with(
            target=mock_sync, args=("idea-promote",), daemon=True,
        )
        mock_thread.start.assert_called_once()

    @patch("nexus.tui.app._tui_sync")
    def test_tui_sync_background_waits_for_previous(self, mock_sync):
        """_tui_sync_background should join any previous sync thread before starting new one."""
        from nexus.tui import _tui_sync_background, _set_sync_thread
        old_thread = MagicMock()
        old_thread.is_alive.return_value = True
        _set_sync_thread(old_thread)
        with patch("nexus.tui.app.threading") as mock_threading:
            mock_thread = MagicMock()
            mock_threading.Thread.return_value = mock_thread
            _tui_sync_background("app-edit")
        old_thread.join.assert_called_once_with(timeout=5)
        _set_sync_thread(None)  # Cleanup


@unittest.skipUnless(HAS_TEXTUAL, "textual not installed")
class TestTuiQuickSync(unittest.TestCase):
    """_tui_sync should use quick_sync for specific actions."""

    @patch("nexus.tui.app.quick_sync")
    @patch("nexus.tui.app.auto_sync_registry")
    def test_codex_edit_uses_quick_sync(self, mock_full, mock_quick):
        mock_quick.return_value = True
        from nexus.tui import _tui_sync
        _tui_sync("codex-edit")
        mock_quick.assert_called_once()
        files_arg = mock_quick.call_args[0][1]
        self.assertEqual(files_arg, ["data/codex/"])
        mock_full.assert_not_called()

    @patch("nexus.tui.app.quick_sync")
    @patch("nexus.tui.app.auto_sync_registry")
    def test_idea_add_uses_quick_sync(self, mock_full, mock_quick):
        mock_quick.return_value = True
        from nexus.tui import _tui_sync
        _tui_sync("idea-add")
        mock_quick.assert_called_once()
        files_arg = mock_quick.call_args[0][1]
        self.assertEqual(files_arg, ["data/ideas.yml", "data/projects.yml"])

    @patch("nexus.tui.app.quick_sync")
    @patch("nexus.tui.app.auto_sync_registry")
    def test_scan_uses_full_sync(self, mock_full, mock_quick):
        mock_full.return_value = True
        from nexus.tui import _tui_sync
        _tui_sync("scan")
        mock_full.assert_called_once()
        mock_quick.assert_not_called()


@unittest.skipUnless(HAS_TEXTUAL, "textual not installed")
class TestRunTuiExceptionResilience(unittest.TestCase):
    """run_tui must not crash on unhandled exceptions from cmd_* functions.

    Every action handler only catches (KeyboardInterrupt, EOFError).
    Any other exception kills the loop and the TUI never reopens.
    """

    @patch("nexus.tui.app._tui_sync_background")
    @patch("nexus.tui.app.NexusApp")
    def test_cmd_exception_does_not_crash_loop(self, MockApp, _sync):
        """If cmd_codex_edit raises ValueError, run_tui should continue."""
        from nexus.tui import run_tui
        mock_app = MagicMock()
        mock_app.run.side_effect = [("codex_edit", "test-slug"), None]
        MockApp.return_value = mock_app

        with patch("nexus._legacy_main.cmd_codex_edit", side_effect=ValueError("boom")):
            result = run_tui()

        self.assertEqual(result, 0)

    @patch("nexus.tui.app._tui_sync_background")
    @patch("nexus.tui.app.NexusApp")
    def test_cmd_file_not_found_does_not_crash_loop(self, MockApp, _sync):
        """If cmd raises FileNotFoundError, run_tui should continue."""
        from nexus.tui import run_tui
        mock_app = MagicMock()
        mock_app.run.side_effect = [("idea_edit", "abc123"), None]
        MockApp.return_value = mock_app

        with patch("nexus._legacy_main.cmd_idea_edit", side_effect=FileNotFoundError("gone")):
            result = run_tui()

        self.assertEqual(result, 0)

    @patch("nexus.tui.app._tui_sync_background")
    @patch("nexus.tui.app.NexusApp")
    def test_app_edit_exception_does_not_crash_loop(self, MockApp, _sync):
        """If cmd_app_edit raises, run_tui should continue."""
        from nexus.tui import run_tui
        mock_app = MagicMock()
        mock_app.run.side_effect = [("app_edit", "my-app"), None]
        MockApp.return_value = mock_app

        with patch("nexus._legacy_main.cmd_app_edit", side_effect=RuntimeError("bad")):
            result = run_tui()

        self.assertEqual(result, 0)


@unittest.skipUnless(HAS_TEXTUAL, "textual not installed")
class TestRunTuiNoEarlyReturn(unittest.TestCase):
    """Action handlers must not 'return 1' — should continue the loop instead."""

    @patch("nexus.tui.app._tui_sync_background")
    @patch("nexus.tui.app.NexusApp")
    def test_note_not_found_returns_to_tui(self, MockApp, _sync):
        """'note' action with unresolved project should return to TUI, not exit."""
        from nexus.tui import run_tui
        mock_app = MagicMock()
        mock_app.run.side_effect = [("note", "nonexistent"), None]
        MockApp.return_value = mock_app

        with patch("nexus.tui.app.resolve_project", return_value=(None, [])):
            result = run_tui()

        self.assertEqual(result, 0)  # Should return 0, not 1

    @patch("nexus.tui.app._tui_sync_background")
    @patch("nexus.tui.app.NexusApp")
    def test_remove_not_found_returns_to_tui(self, MockApp, _sync):
        """'remove' action with unresolved project should return to TUI, not exit."""
        from nexus.tui import run_tui
        mock_app = MagicMock()
        mock_app.run.side_effect = [("remove", "nonexistent"), None]
        MockApp.return_value = mock_app

        with patch("nexus.tui.app.resolve_project", return_value=(None, [])):
            result = run_tui()

        self.assertEqual(result, 0)  # Should return 0, not 1


@unittest.skipUnless(HAS_TEXTUAL, "textual not installed")
class TestGroupHeaderSkip(unittest.TestCase):
    def test_is_group_row_detects_prefix(self):
        from textual.widgets.data_table import RowKey
        from nexus.tui import NexusApp
        app = NexusApp.__new__(NexusApp)
        app._group_keys = {RowKey("_group:tech")}
        self.assertTrue(app._is_group_row(RowKey("_group:tech")))
        self.assertFalse(app._is_group_row(RowKey("nexus")))


class TestFilterParser(unittest.TestCase):
    def test_plain_text(self):
        from nexus.tui import _parse_filter
        result = _parse_filter("nexus")
        self.assertEqual(result, {"text": "nexus", "d": None, "n": None, "k": None})

    def test_domain_prefix(self):
        from nexus.tui import _parse_filter
        result = _parse_filter("d:tech")
        self.assertEqual(result, {"text": "", "d": "tech", "n": None, "k": None})

    def test_nature_alias(self):
        from nexus.tui import _parse_filter
        result = _parse_filter("n:tool")
        self.assertEqual(result, {"text": "", "d": None, "n": "ferramenta", "k": None})

    def test_combined(self):
        from nexus.tui import _parse_filter
        result = _parse_filter("d:tech n:ferramenta comfy")
        self.assertEqual(result, {"text": "comfy", "d": "tech", "n": "ferramenta", "k": None})

    def test_nature_alias_ctx(self):
        from nexus.tui import _parse_filter
        result = _parse_filter("n:ctx")
        self.assertEqual(result, {"text": "", "d": None, "n": "contexto", "k": None})

    def test_nature_alias_app(self):
        from nexus.tui import _parse_filter
        result = _parse_filter("n:app")
        self.assertEqual(result, {"text": "", "d": None, "n": "companion", "k": None})

    def test_kind_prefix(self):
        from nexus.tui import _parse_filter
        result = _parse_filter("k:guia")
        self.assertEqual(result, {"text": "", "d": None, "n": None, "k": "guia"})


class TestFilterSuggester(unittest.TestCase):
    def test_suggests_domain_after_d_prefix(self):
        import asyncio
        from nexus.tui import FilterSuggester
        s = FilterSuggester()
        result = asyncio.run(s.get_suggestion("d:te"))
        self.assertEqual(result, "d:tech")

    def test_suggests_nature_after_n_prefix(self):
        import asyncio
        from nexus.tui import FilterSuggester
        s = FilterSuggester()
        result = asyncio.run(s.get_suggestion("n:fer"))
        self.assertEqual(result, "n:ferramenta")

    def test_no_suggestion_for_plain_text(self):
        import asyncio
        from nexus.tui import FilterSuggester
        s = FilterSuggester()
        result = asyncio.run(s.get_suggestion("nexus"))
        self.assertIsNone(result)

    def test_suggests_after_first_prefix(self):
        import asyncio
        from nexus.tui import FilterSuggester
        s = FilterSuggester()
        result = asyncio.run(s.get_suggestion("d:tech n:fer"))
        self.assertEqual(result, "d:tech n:ferramenta")


if __name__ == "__main__":
    unittest.main()
