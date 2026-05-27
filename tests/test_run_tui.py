"""
Tests for run_tui() event loop — nexus/tui.py lines 1336-1688.

Strategy: mock NexusApp so the first call returns an action result and the
second call returns None (breaking the loop). Patch all side-effecting
functions called inside each handler.
"""
import unittest
from unittest.mock import MagicMock, patch, call

try:
    from nexus.tui import run_tui
    HAS_TEXTUAL = True
except ImportError:
    HAS_TEXTUAL = False


def _make_app_class(results):
    """Return a mock NexusApp class whose instances yield results in order."""
    results_iter = iter(results)

    class FakeApp:
        def __init__(self, initial_tab="ideas"):
            self.initial_tab = initial_tab

        def run(self):
            try:
                return next(results_iter)
            except StopIteration:
                return None

    return FakeApp


@unittest.skipUnless(HAS_TEXTUAL, "textual not installed")
class TestRunTuiBasic(unittest.TestCase):
    """Basic run_tui loop control tests."""

    def test_run_tui_returns_zero_on_none_result(self):
        """run_tui: app.run() returns None → return 0 immediately."""
        FakeApp = _make_app_class([None])
        with patch("nexus.tui.app.NexusApp", FakeApp):
            result = run_tui()
        self.assertEqual(result, 0)

    def test_run_tui_unknown_action_returns_zero(self):
        """run_tui: unknown action → else branch → return 0 (line 1687-1688)."""
        FakeApp = _make_app_class([("unknown_action", None)])
        with patch("nexus.tui.app.NexusApp", FakeApp):
            result = run_tui()
        self.assertEqual(result, 0)


@unittest.skipUnless(HAS_TEXTUAL, "textual not installed")
class TestRunTuiLaunch(unittest.TestCase):
    """Tests for 'launch' action (lines 1349-1357)."""

    def test_launch_calls_execvp(self):
        """run_tui: launch action → chdir + execvp."""
        FakeApp = _make_app_class([("launch", {"path": "/myproj", "cli": "claude"})])
        with patch("nexus.tui.app.NexusApp", FakeApp), \
             patch("os.chdir") as mock_chdir, \
             patch("os.execvp") as mock_execvp:
            run_tui()
        mock_chdir.assert_called_once_with("/myproj")
        mock_execvp.assert_called_once_with("claude", ["claude"])

    def test_launch_execvp_not_found_returns_one(self):
        """run_tui: launch → execvp raises FileNotFoundError → return 1 (line 1355-1357)."""
        FakeApp = _make_app_class([("launch", {"path": "/myproj", "cli": "missing-cli"})])
        with patch("nexus.tui.app.NexusApp", FakeApp), \
             patch("os.chdir"), \
             patch("os.execvp", side_effect=FileNotFoundError("not found")):
            result = run_tui()
        self.assertEqual(result, 1)


@unittest.skipUnless(HAS_TEXTUAL, "textual not installed")
class TestRunTuiLaunchMissing(unittest.TestCase):
    """Tests for 'launch_missing' action (lines 1359-1413).

    find_moved_project and move_project are local imports inside run_tui(),
    so they must be patched at source module level (nexus.relocate / nexus.registry).
    """

    def test_launch_missing_no_candidates_empty_input_returns_zero(self):
        """launch_missing: no candidates, user gives empty path → return 0 (line 1397-1399)."""
        FakeApp = _make_app_class([("launch_missing", "/old/path")])
        with patch("nexus.tui.app.NexusApp", FakeApp), \
             patch("nexus.relocate.find_moved_project", return_value=[]), \
             patch("builtins.input", return_value=""):
            result = run_tui()
        self.assertEqual(result, 0)

    def test_launch_missing_single_candidate_user_confirms(self):
        """launch_missing: one candidate, user confirms → move_project + scan_one + continue."""
        # Second call returns None to break loop
        FakeApp = _make_app_class([("launch_missing", "/old/path"), None])
        mock_move_result = MagicMock()
        mock_move_result.name = "MyProj"

        mock_path_inst = MagicMock()
        mock_path_inst.exists.return_value = True

        with patch("nexus.tui.app.NexusApp", FakeApp), \
             patch("nexus.relocate.find_moved_project", return_value=["/new/path"]), \
             patch("builtins.input", return_value=""), \
             patch("nexus.registry.move_project", return_value=mock_move_result) as mock_move, \
             patch("nexus.tui.app._tui_sync_background") as mock_sync, \
             patch("nexus.tui.app.scan_one") as mock_scan, \
             patch("nexus.tui.app.Path", return_value=mock_path_inst):
            result = run_tui()
        self.assertEqual(result, 0)
        mock_scan.assert_called_once_with("/new/path")

    def test_launch_missing_single_candidate_user_types_n(self):
        """launch_missing: one candidate, user types 'n' → no_path → ask manual input."""
        FakeApp = _make_app_class([("launch_missing", "/old/path")])
        # User types "n" to reject, then empty for manual → return 0
        with patch("nexus.tui.app.NexusApp", FakeApp), \
             patch("nexus.relocate.find_moved_project", return_value=["/new/path"]), \
             patch("builtins.input", side_effect=["n", ""]):
            result = run_tui()
        self.assertEqual(result, 0)

    def test_launch_missing_keyboard_interrupt_on_confirm(self):
        """launch_missing: KeyboardInterrupt on confirm → return 0 (line 1372-1374)."""
        FakeApp = _make_app_class([("launch_missing", "/old/path")])
        with patch("nexus.tui.app.NexusApp", FakeApp), \
             patch("nexus.relocate.find_moved_project", return_value=["/new/path"]), \
             patch("builtins.input", side_effect=KeyboardInterrupt):
            result = run_tui()
        self.assertEqual(result, 0)

    def test_launch_missing_multiple_candidates_valid_choice(self):
        """launch_missing: multiple candidates, user picks valid index → scan + continue."""
        FakeApp = _make_app_class([("launch_missing", "/old/path"), None])
        mock_move_result = MagicMock()
        mock_move_result.name = "MyProj"

        mock_path_inst = MagicMock()
        mock_path_inst.exists.return_value = True

        with patch("nexus.tui.app.NexusApp", FakeApp), \
             patch("nexus.relocate.find_moved_project", return_value=["/new/path1", "/new/path2"]), \
             patch("builtins.input", return_value="1"), \
             patch("nexus.registry.move_project", return_value=mock_move_result) as mock_move, \
             patch("nexus.tui.app._tui_sync_background"), \
             patch("nexus.tui.app.scan_one") as mock_scan, \
             patch("nexus.tui.app.Path", return_value=mock_path_inst):
            result = run_tui()
        self.assertEqual(result, 0)
        mock_scan.assert_called_once_with("/new/path1")

    def test_launch_missing_multiple_candidates_keyboard_interrupt(self):
        """launch_missing: multiple candidates, KeyboardInterrupt on choice → return 0."""
        FakeApp = _make_app_class([("launch_missing", "/old/path")])
        with patch("nexus.tui.app.NexusApp", FakeApp), \
             patch("nexus.relocate.find_moved_project", return_value=["/new/path1", "/new/path2"]), \
             patch("builtins.input", side_effect=KeyboardInterrupt):
            result = run_tui()
        self.assertEqual(result, 0)

    def test_launch_missing_multiple_candidates_choice_zero(self):
        """launch_missing: multiple candidates, choice=0 → manual input → empty → return 0."""
        FakeApp = _make_app_class([("launch_missing", "/old/path")])
        with patch("nexus.tui.app.NexusApp", FakeApp), \
             patch("nexus.relocate.find_moved_project", return_value=["/c1", "/c2"]), \
             patch("builtins.input", side_effect=["0", ""]):
            result = run_tui()
        self.assertEqual(result, 0)

    def test_launch_missing_no_candidates_path_not_exist_returns_zero(self):
        """launch_missing: no candidates, user gives non-existent path → return 0."""
        FakeApp = _make_app_class([("launch_missing", "/old/path")])
        with patch("nexus.tui.app.NexusApp", FakeApp), \
             patch("nexus.relocate.find_moved_project", return_value=[]), \
             patch("builtins.input", return_value="/nonexistent/path"), \
             patch("nexus.tui.app.Path") as mock_path_cls:
            # Make path not exist
            mock_path_instance = MagicMock()
            mock_path_instance.exists.return_value = False
            mock_path_cls.return_value = mock_path_instance
            result = run_tui()
        self.assertEqual(result, 0)

    def test_launch_missing_no_data_skips_move(self):
        """launch_missing: data is None (falsy), move_project not called."""
        FakeApp = _make_app_class([("launch_missing", None), None])
        with patch("nexus.tui.app.NexusApp", FakeApp), \
             patch("nexus.relocate.find_moved_project", return_value=[]), \
             patch("builtins.input", return_value="/new/path"), \
             patch("nexus.tui.app.Path") as mock_path_cls, \
             patch("nexus.tui.app.scan_one") as mock_scan:
            mock_path_instance = MagicMock()
            mock_path_instance.exists.return_value = True
            mock_path_cls.return_value = mock_path_instance
            result = run_tui()
        # scan_one called with the new path
        mock_scan.assert_called()

    def test_launch_missing_manual_input_keyboard_interrupt(self):
        """launch_missing: no candidates, KeyboardInterrupt on manual path input → return 0 (lines 1393-1395)."""
        FakeApp = _make_app_class([("launch_missing", "/old/path")])
        with patch("nexus.tui.app.NexusApp", FakeApp), \
             patch("nexus.relocate.find_moved_project", return_value=[]), \
             patch("builtins.input", side_effect=KeyboardInterrupt):
            result = run_tui()
        self.assertEqual(result, 0)

    def test_launch_missing_move_returns_none_uses_overrides(self):
        """launch_missing: move_project returns None → try path override (lines 1407-1408)."""
        FakeApp = _make_app_class([("launch_missing", "/old/path"), None])
        with patch("nexus.tui.app.NexusApp", FakeApp), \
             patch("nexus.relocate.find_moved_project", return_value=[]), \
             patch("builtins.input", return_value="/new/path"), \
             patch("nexus.tui.app.Path") as mock_path_cls, \
             patch("nexus.registry.move_project", return_value=None) as mock_move, \
             patch("nexus.tui.app.set_project_path_override", return_value=False) as mock_sppo, \
             patch("nexus.tui.app.set_path_override") as mock_spo, \
             patch("nexus.tui.app.scan_one"):
            mock_path_instance = MagicMock()
            mock_path_instance.exists.return_value = True
            mock_path_cls.return_value = mock_path_instance
            result = run_tui()
        mock_sppo.assert_called_once_with("/old/path", "/new/path")
        mock_spo.assert_called_once_with("/old/path", "/new/path")


@unittest.skipUnless(HAS_TEXTUAL, "textual not installed")
class TestRunTuiEdit(unittest.TestCase):
    """Tests for 'edit' action (lines 1415-1425)."""

    def test_edit_calls_cmd_edit(self):
        """run_tui: edit → cmd_edit called → _tui_sync_background."""
        FakeApp = _make_app_class([("edit", "myproj"), None])
        mock_cmd_edit = MagicMock()
        with patch("nexus.tui.app.NexusApp", FakeApp), \
             patch("nexus.tui.app._tui_sync_background") as mock_sync, \
             patch("nexus._legacy_main.cmd_edit", mock_cmd_edit, create=True):
            # Patch the module-level import that happens inside run_tui_loop
            import sys
            import nexus._legacy_main as main_mod
            original = getattr(main_mod, "cmd_edit", None)
            main_mod.cmd_edit = mock_cmd_edit
            try:
                result = run_tui()
            finally:
                if original is not None:
                    main_mod.cmd_edit = original
                else:
                    del main_mod.cmd_edit
        self.assertEqual(result, 0)
        mock_sync.assert_any_call("edit")

    def test_edit_keyboard_interrupt_continues(self):
        """run_tui: edit → KeyboardInterrupt → _tui_sync_background still called."""
        FakeApp = _make_app_class([("edit", "myproj"), None])
        import nexus._legacy_main as main_mod
        original = getattr(main_mod, "cmd_edit", None)
        main_mod.cmd_edit = MagicMock(side_effect=KeyboardInterrupt)
        try:
            with patch("nexus.tui.app.NexusApp", FakeApp), \
                 patch("nexus.tui.app._tui_sync_background") as mock_sync:
                result = run_tui()
        finally:
            if original is not None:
                main_mod.cmd_edit = original
            else:
                del main_mod.cmd_edit
        mock_sync.assert_any_call("edit")

    def test_edit_exception_continues(self):
        """run_tui: edit → generic Exception → _tui_sync_background still called."""
        FakeApp = _make_app_class([("edit", "myproj"), None])
        import nexus._legacy_main as main_mod
        original = getattr(main_mod, "cmd_edit", None)
        main_mod.cmd_edit = MagicMock(side_effect=ValueError("bad"))
        try:
            with patch("nexus.tui.app.NexusApp", FakeApp), \
                 patch("nexus.tui.app._tui_sync_background") as mock_sync:
                result = run_tui()
        finally:
            if original is not None:
                main_mod.cmd_edit = original
            else:
                del main_mod.cmd_edit
        mock_sync.assert_any_call("edit")


@unittest.skipUnless(HAS_TEXTUAL, "textual not installed")
class TestRunTuiNote(unittest.TestCase):
    """Tests for 'note' action (lines 1427-1443)."""

    def test_note_no_match_continues(self):
        """run_tui: note → resolve_project returns None → continue loop (line 1429-1432)."""
        FakeApp = _make_app_class([("note", "myproj"), None])
        with patch("nexus.tui.app.NexusApp", FakeApp), \
             patch("nexus.tui.app.resolve_project", return_value=(None, None)):
            result = run_tui()
        self.assertEqual(result, 0)

    def test_note_with_match_keyboard_interrupt(self):
        """run_tui: note → matched, then KeyboardInterrupt on input → continue."""
        FakeApp = _make_app_class([("note", "myproj"), None])
        matched = MagicMock()
        matched.path = "/myproj"
        matched.name = "MyProj"
        with patch("nexus.tui.app.NexusApp", FakeApp), \
             patch("nexus.tui.app.resolve_project", return_value=(matched, None)), \
             patch("builtins.input", side_effect=KeyboardInterrupt):
            result = run_tui()
        self.assertEqual(result, 0)

    def test_note_with_match_and_note_entered(self):
        """run_tui: note → matched → user enters note → update_project called."""
        FakeApp = _make_app_class([("note", "myproj"), None])
        matched = MagicMock()
        matched.path = "/myproj"
        matched.name = "MyProj"
        with patch("nexus.tui.app.NexusApp", FakeApp), \
             patch("nexus.tui.app.resolve_project", return_value=(matched, None)), \
             patch("builtins.input", return_value="Minha nota"), \
             patch("nexus.tui.app.update_project") as mock_update, \
             patch("nexus.tui.app._tui_sync_background") as mock_sync:
            result = run_tui()
        self.assertEqual(result, 0)
        mock_update.assert_called_once_with("/myproj", note="Minha nota")
        mock_sync.assert_any_call("note")

    def test_note_with_match_empty_note_no_update(self):
        """run_tui: note → matched → user enters empty note → no update (line 1439)."""
        FakeApp = _make_app_class([("note", "myproj"), None])
        matched = MagicMock()
        matched.path = None
        matched.name = "MyProj"
        with patch("nexus.tui.app.NexusApp", FakeApp), \
             patch("nexus.tui.app.resolve_project", return_value=(matched, None)), \
             patch("builtins.input", return_value=""), \
             patch("nexus.tui.app.update_project") as mock_update:
            result = run_tui()
        mock_update.assert_not_called()


@unittest.skipUnless(HAS_TEXTUAL, "textual not installed")
class TestRunTuiRemove(unittest.TestCase):
    """Tests for 'remove' action (lines 1445-1470)."""

    def test_remove_no_match_continues(self):
        """run_tui: remove → no match → continue loop (line 1449-1452)."""
        FakeApp = _make_app_class([("remove", "myproj"), None])
        with patch("nexus.tui.app.NexusApp", FakeApp), \
             patch("nexus.tui.app.resolve_project", return_value=(None, None)):
            result = run_tui()
        self.assertEqual(result, 0)

    def test_remove_keyboard_interrupt_on_confirm(self):
        """run_tui: remove → matched, KeyboardInterrupt on confirm → continue."""
        FakeApp = _make_app_class([("remove", "myproj"), None])
        matched = MagicMock()
        matched.name = "MyProj"
        matched.path = "/myproj"
        matched.slug = "myproj"
        with patch("nexus.tui.app.NexusApp", FakeApp), \
             patch("nexus.tui.app.resolve_project", return_value=(matched, None)), \
             patch("builtins.input", side_effect=KeyboardInterrupt):
            result = run_tui()
        self.assertEqual(result, 0)

    def test_remove_confirm_s_removes_project(self):
        """run_tui: remove → matched, confirm 's' → remove_project called."""
        FakeApp = _make_app_class([("remove", "myproj"), None])
        matched = MagicMock()
        matched.name = "MyProj"
        matched.path = "/myproj"
        matched.slug = "myproj"
        with patch("nexus.tui.app.NexusApp", FakeApp), \
             patch("nexus.tui.app.resolve_project", return_value=(matched, None)), \
             patch("builtins.input", return_value="s"), \
             patch("nexus.tui.app.resolve_path_for_entry", return_value="/myproj"), \
             patch("nexus.tui.app.resolve_project_path", return_value="/myproj"), \
             patch("nexus.tui.app._tui_sync_background") as mock_sync:
            # Patch the local imports inside the function
            import nexus.hooks as hooks_mod
            import nexus.registry as registry_mod
            original_remove_git = getattr(hooks_mod, "remove_git_hook", None)
            original_remove_claude = getattr(hooks_mod, "remove_claude_hook", None)
            original_remove_proj = getattr(registry_mod, "remove_project", None)
            mock_rg = MagicMock()
            mock_rc = MagicMock()
            mock_rp = MagicMock()
            hooks_mod.remove_git_hook = mock_rg
            hooks_mod.remove_claude_hook = mock_rc
            registry_mod.remove_project = mock_rp
            try:
                result = run_tui()
            finally:
                if original_remove_git is not None:
                    hooks_mod.remove_git_hook = original_remove_git
                if original_remove_claude is not None:
                    hooks_mod.remove_claude_hook = original_remove_claude
                if original_remove_proj is not None:
                    registry_mod.remove_project = original_remove_proj
        self.assertEqual(result, 0)
        mock_rp.assert_called_once()
        mock_sync.assert_any_call("remove")

    def test_remove_confirm_not_s_prints_cancelado(self):
        """run_tui: remove → matched, confirm 'n' → 'Cancelado.' (line 1468-1469)."""
        FakeApp = _make_app_class([("remove", "myproj"), None])
        matched = MagicMock()
        matched.name = "MyProj"
        matched.path = "/myproj"
        matched.slug = "myproj"
        with patch("nexus.tui.app.NexusApp", FakeApp), \
             patch("nexus.tui.app.resolve_project", return_value=(matched, None)), \
             patch("builtins.input", return_value="n"), \
             patch("builtins.print") as mock_print:
            result = run_tui()
        self.assertEqual(result, 0)
        printed = " ".join(str(c) for c in mock_print.call_args_list)
        self.assertIn("Cancelado", printed)

    def test_remove_no_resolve_path_skips_hooks(self):
        """run_tui: remove → confirm 's', resolve_path_for_entry → None → skip hooks."""
        FakeApp = _make_app_class([("remove", "myproj"), None])
        matched = MagicMock()
        matched.name = "MyProj"
        matched.path = "/myproj"
        matched.slug = "myproj"
        with patch("nexus.tui.app.NexusApp", FakeApp), \
             patch("nexus.tui.app.resolve_project", return_value=(matched, None)), \
             patch("builtins.input", return_value="s"), \
             patch("nexus.tui.app.resolve_path_for_entry", return_value=None), \
             patch("nexus.tui.app._tui_sync_background"):
            import nexus.registry as registry_mod
            original_remove_proj = getattr(registry_mod, "remove_project", None)
            registry_mod.remove_project = MagicMock()
            try:
                result = run_tui()
            finally:
                if original_remove_proj is not None:
                    registry_mod.remove_project = original_remove_proj
        self.assertEqual(result, 0)


@unittest.skipUnless(HAS_TEXTUAL, "textual not installed")
class TestRunTuiAdd(unittest.TestCase):
    """Tests for 'add' action (lines 1472-1482)."""

    def test_add_calls_cmd_add(self):
        """run_tui: add → cmd_add called → _tui_sync_background."""
        FakeApp = _make_app_class([("add", None), None])
        import nexus._legacy_main as main_mod
        original = getattr(main_mod, "cmd_add", None)
        mock_cmd_add = MagicMock()
        main_mod.cmd_add = mock_cmd_add
        try:
            with patch("nexus.tui.app.NexusApp", FakeApp), \
                 patch("nexus.tui.app._tui_sync_background") as mock_sync:
                result = run_tui()
        finally:
            if original is not None:
                main_mod.cmd_add = original
            else:
                del main_mod.cmd_add
        mock_cmd_add.assert_called_once()
        mock_sync.assert_any_call("add")

    def test_add_keyboard_interrupt(self):
        """run_tui: add → KeyboardInterrupt → _tui_sync_background still called."""
        FakeApp = _make_app_class([("add", None), None])
        import nexus._legacy_main as main_mod
        original = getattr(main_mod, "cmd_add", None)
        main_mod.cmd_add = MagicMock(side_effect=KeyboardInterrupt)
        try:
            with patch("nexus.tui.app.NexusApp", FakeApp), \
                 patch("nexus.tui.app._tui_sync_background") as mock_sync:
                result = run_tui()
        finally:
            if original is not None:
                main_mod.cmd_add = original
            else:
                del main_mod.cmd_add
        mock_sync.assert_any_call("add")

    def test_add_exception(self):
        """run_tui: add → generic Exception → _tui_sync_background still called."""
        FakeApp = _make_app_class([("add", None), None])
        import nexus._legacy_main as main_mod
        original = getattr(main_mod, "cmd_add", None)
        main_mod.cmd_add = MagicMock(side_effect=RuntimeError("bad"))
        try:
            with patch("nexus.tui.app.NexusApp", FakeApp), \
                 patch("nexus.tui.app._tui_sync_background") as mock_sync:
                result = run_tui()
        finally:
            if original is not None:
                main_mod.cmd_add = original
            else:
                del main_mod.cmd_add
        mock_sync.assert_any_call("add")


@unittest.skipUnless(HAS_TEXTUAL, "textual not installed")
class TestRunTuiIdeaActions(unittest.TestCase):
    """Tests for idea_add, idea_edit, idea_remove, idea_promote (lines 1484-1532)."""

    def _run_action(self, action, data, cmd_name, keyboard_interrupt=False, exception=False):
        """Helper to run an idea action and verify sync is called."""
        FakeApp = _make_app_class([(action, data), None])
        import nexus._legacy_main as main_mod
        original = getattr(main_mod, cmd_name, None)
        if keyboard_interrupt:
            mock_cmd = MagicMock(side_effect=KeyboardInterrupt)
        elif exception:
            mock_cmd = MagicMock(side_effect=RuntimeError("err"))
        else:
            mock_cmd = MagicMock()
        main_mod.__dict__[cmd_name] = mock_cmd
        try:
            with patch("nexus.tui.app.NexusApp", FakeApp), \
                 patch("nexus.tui.app._tui_sync_background") as mock_sync:
                result = run_tui()
        finally:
            if original is not None:
                main_mod.__dict__[cmd_name] = original
            else:
                del main_mod.__dict__[cmd_name]
        return result, mock_cmd, mock_sync

    def test_idea_add_success(self):
        """run_tui: idea_add → cmd_idea_add called → sync idea-add."""
        result, mock_cmd, mock_sync = self._run_action("idea_add", None, "cmd_idea_add")
        self.assertEqual(result, 0)
        mock_cmd.assert_called_once()
        mock_sync.assert_any_call("idea-add")

    def test_idea_add_keyboard_interrupt(self):
        """run_tui: idea_add → KeyboardInterrupt → sync still called."""
        result, _, mock_sync = self._run_action("idea_add", None, "cmd_idea_add", keyboard_interrupt=True)
        mock_sync.assert_any_call("idea-add")

    def test_idea_add_exception(self):
        """run_tui: idea_add → Exception → sync still called."""
        result, _, mock_sync = self._run_action("idea_add", None, "cmd_idea_add", exception=True)
        mock_sync.assert_any_call("idea-add")

    def test_idea_edit_success(self):
        """run_tui: idea_edit → cmd_idea_edit called → sync idea-edit."""
        result, mock_cmd, mock_sync = self._run_action("idea_edit", "myidea", "cmd_idea_edit")
        self.assertEqual(result, 0)
        mock_cmd.assert_called_once()
        mock_sync.assert_any_call("idea-edit")

    def test_idea_edit_keyboard_interrupt(self):
        """run_tui: idea_edit → KeyboardInterrupt → sync still called."""
        result, _, mock_sync = self._run_action("idea_edit", "myidea", "cmd_idea_edit", keyboard_interrupt=True)
        mock_sync.assert_any_call("idea-edit")

    def test_idea_edit_exception(self):
        """run_tui: idea_edit line 1504 → Exception → sync still called."""
        result, _, mock_sync = self._run_action("idea_edit", "myidea", "cmd_idea_edit", exception=True)
        mock_sync.assert_any_call("idea-edit")

    def test_idea_remove_success(self):
        """run_tui: idea_remove → cmd_idea_remove called → sync idea-remove."""
        result, mock_cmd, mock_sync = self._run_action("idea_remove", "myidea", "cmd_idea_remove")
        mock_cmd.assert_called_once()
        mock_sync.assert_any_call("idea-remove")

    def test_idea_remove_keyboard_interrupt(self):
        """run_tui: idea_remove → KeyboardInterrupt → sync still called (line 1515-1516)."""
        result, _, mock_sync = self._run_action("idea_remove", "myidea", "cmd_idea_remove", keyboard_interrupt=True)
        mock_sync.assert_any_call("idea-remove")

    def test_idea_remove_exception(self):
        """run_tui: idea_remove → Exception → sync still called (line 1517-1518)."""
        result, _, mock_sync = self._run_action("idea_remove", "myidea", "cmd_idea_remove", exception=True)
        mock_sync.assert_any_call("idea-remove")

    def test_idea_promote_success(self):
        """run_tui: idea_promote → cmd_idea_promote → sync idea-promote."""
        with patch("builtins.input", return_value=""):
            result, mock_cmd, mock_sync = self._run_action("idea_promote", "myidea", "cmd_idea_promote")
        mock_cmd.assert_called_once()
        mock_sync.assert_any_call("idea-promote")

    def test_idea_promote_keyboard_interrupt(self):
        """run_tui: idea_promote → KeyboardInterrupt → sync still called."""
        with patch("builtins.input", return_value=""):
            result, _, mock_sync = self._run_action("idea_promote", "myidea", "cmd_idea_promote", keyboard_interrupt=True)
        mock_sync.assert_any_call("idea-promote")

    def test_idea_promote_exception(self):
        """run_tui: idea_promote → Exception → sync still called."""
        with patch("builtins.input", return_value=""):
            result, _, mock_sync = self._run_action("idea_promote", "myidea", "cmd_idea_promote", exception=True)
        mock_sync.assert_any_call("idea-promote")

    def test_idea_promote_as_app(self):
        """run_tui: idea_promote with 'a' → app=True, next_tab=apps."""
        FakeApp = _make_app_class([("idea_promote", "abc123"), None])
        import nexus._legacy_main as main_mod
        mock_cmd = MagicMock()
        original = main_mod.__dict__.get("cmd_idea_promote")
        main_mod.__dict__["cmd_idea_promote"] = mock_cmd
        try:
            with (
                patch("nexus.tui.app.NexusApp", FakeApp),
                patch("nexus.tui.app._tui_sync_background") as mock_sync,
                patch("builtins.input", return_value="a"),
            ):
                run_tui()
        finally:
            if original is not None:
                main_mod.__dict__["cmd_idea_promote"] = original
            else:
                del main_mod.__dict__["cmd_idea_promote"]

        # cmd_idea_promote called with app=True
        ns = mock_cmd.call_args[0][0]
        self.assertTrue(ns.app)
        self.assertEqual(ns.query, "abc123")

    def test_idea_promote_as_project_default(self):
        """run_tui: idea_promote with Enter → app=False (default project)."""
        FakeApp = _make_app_class([("idea_promote", "abc123"), None])
        import nexus._legacy_main as main_mod
        mock_cmd = MagicMock()
        original = main_mod.__dict__.get("cmd_idea_promote")
        main_mod.__dict__["cmd_idea_promote"] = mock_cmd
        try:
            with (
                patch("nexus.tui.app.NexusApp", FakeApp),
                patch("nexus.tui.app._tui_sync_background"),
                patch("builtins.input", return_value=""),
            ):
                run_tui()
        finally:
            if original is not None:
                main_mod.__dict__["cmd_idea_promote"] = original
            else:
                del main_mod.__dict__["cmd_idea_promote"]

        ns = mock_cmd.call_args[0][0]
        self.assertFalse(ns.app)

    def test_idea_promote_as_app_next_tab(self):
        """run_tui: idea_promote with 'a' → NexusApp re-launched with initial_tab='apps'."""
        calls = []
        class TrackingApp:
            def __init__(self, initial_tab="ideas"):
                calls.append(initial_tab)
            def run(self):
                if len(calls) == 1:
                    return ("idea_promote", "abc123")
                return None

        import nexus._legacy_main as main_mod
        mock_cmd = MagicMock()
        original = main_mod.__dict__.get("cmd_idea_promote")
        main_mod.__dict__["cmd_idea_promote"] = mock_cmd
        try:
            with (
                patch("nexus.tui.app.NexusApp", TrackingApp),
                patch("nexus.tui.app._tui_sync_background"),
                patch("builtins.input", return_value="a"),
            ):
                run_tui()
        finally:
            if original is not None:
                main_mod.__dict__["cmd_idea_promote"] = original
            else:
                del main_mod.__dict__["cmd_idea_promote"]

        # Second NexusApp launch should have initial_tab="apps"
        self.assertEqual(calls[1], "apps")


@unittest.skipUnless(HAS_TEXTUAL, "textual not installed")
class TestRunTuiCodexActions(unittest.TestCase):
    """Tests for codex_add, codex_edit, codex_remove (lines 1534-1570)."""

    def _run_action(self, action, data, cmd_name, exc=None):
        FakeApp = _make_app_class([(action, data), None])
        import nexus._legacy_main as main_mod
        original = main_mod.__dict__.get(cmd_name)
        if exc:
            mock_cmd = MagicMock(side_effect=exc)
        else:
            mock_cmd = MagicMock()
        main_mod.__dict__[cmd_name] = mock_cmd
        try:
            with patch("nexus.tui.app.NexusApp", FakeApp), \
                 patch("nexus.tui.app._tui_sync_background") as mock_sync:
                result = run_tui()
        finally:
            if original is not None:
                main_mod.__dict__[cmd_name] = original
            else:
                del main_mod.__dict__[cmd_name]
        return result, mock_cmd, mock_sync

    def test_codex_add_success(self):
        """run_tui: codex_add → cmd_codex_add called → sync codex-add."""
        result, mock_cmd, mock_sync = self._run_action("codex_add", None, "cmd_codex_add")
        mock_cmd.assert_called_once()
        mock_sync.assert_any_call("codex-add")

    def test_codex_add_keyboard_interrupt(self):
        """run_tui: codex_add → KeyboardInterrupt → sync still called (line 1542)."""
        result, _, mock_sync = self._run_action("codex_add", None, "cmd_codex_add", exc=KeyboardInterrupt)
        mock_sync.assert_any_call("codex-add")

    def test_codex_add_exception(self):
        """run_tui: codex_add → Exception → sync still called (line 1543-1544)."""
        result, _, mock_sync = self._run_action("codex_add", None, "cmd_codex_add", exc=RuntimeError("err"))
        mock_sync.assert_any_call("codex-add")

    def test_codex_edit_success(self):
        """run_tui: codex_edit → cmd_codex_edit called → sync codex-edit."""
        result, mock_cmd, mock_sync = self._run_action("codex_edit", "myentry", "cmd_codex_edit")
        mock_cmd.assert_called_once()
        mock_sync.assert_any_call("codex-edit")

    def test_codex_edit_keyboard_interrupt(self):
        """run_tui: codex_edit → KeyboardInterrupt → sync still called (line 1554)."""
        result, _, mock_sync = self._run_action("codex_edit", "myentry", "cmd_codex_edit", exc=KeyboardInterrupt)
        mock_sync.assert_any_call("codex-edit")

    def test_codex_edit_exception(self):
        """run_tui: codex_edit → Exception → sync still called (line 1555-1556)."""
        result, _, mock_sync = self._run_action("codex_edit", "myentry", "cmd_codex_edit", exc=ValueError("err"))
        mock_sync.assert_any_call("codex-edit")

    def test_codex_remove_success(self):
        """run_tui: codex_remove → cmd_codex_remove called → sync codex-remove."""
        result, mock_cmd, mock_sync = self._run_action("codex_remove", "myentry", "cmd_codex_remove")
        mock_cmd.assert_called_once()
        mock_sync.assert_any_call("codex-remove")

    def test_codex_remove_keyboard_interrupt(self):
        """run_tui: codex_remove → KeyboardInterrupt → sync still called (line 1561-1562)."""
        result, _, mock_sync = self._run_action("codex_remove", "myentry", "cmd_codex_remove", exc=KeyboardInterrupt)
        mock_sync.assert_any_call("codex-remove")

    def test_codex_remove_exception(self):
        """run_tui: codex_remove → Exception → sync still called (line 1568-1569)."""
        result, _, mock_sync = self._run_action("codex_remove", "myentry", "cmd_codex_remove", exc=OSError("err"))
        mock_sync.assert_any_call("codex-remove")


@unittest.skipUnless(HAS_TEXTUAL, "textual not installed")
class TestRunTuiAppActions(unittest.TestCase):
    """Tests for app_add, app_edit, app_remove, app_note (lines 1572-1616)."""

    def _run_action(self, action, data, cmd_name, exc=None):
        FakeApp = _make_app_class([(action, data), None])
        import nexus._legacy_main as main_mod
        original = main_mod.__dict__.get(cmd_name)
        if exc:
            mock_cmd = MagicMock(side_effect=exc)
        else:
            mock_cmd = MagicMock()
        main_mod.__dict__[cmd_name] = mock_cmd
        try:
            with patch("nexus.tui.app.NexusApp", FakeApp), \
                 patch("nexus.tui.app._tui_sync_background") as mock_sync:
                result = run_tui()
        finally:
            if original is not None:
                main_mod.__dict__[cmd_name] = original
            else:
                del main_mod.__dict__[cmd_name]
        return result, mock_cmd, mock_sync

    def test_app_add_success(self):
        """run_tui: app_add → cmd_app_add called → sync app-add."""
        result, mock_cmd, mock_sync = self._run_action("app_add", None, "cmd_app_add")
        mock_cmd.assert_called_once()
        mock_sync.assert_any_call("app-add")

    def test_app_add_keyboard_interrupt(self):
        """run_tui: app_add → KeyboardInterrupt → sync still called (line 1578-1579)."""
        result, _, mock_sync = self._run_action("app_add", None, "cmd_app_add", exc=KeyboardInterrupt)
        mock_sync.assert_any_call("app-add")

    def test_app_add_exception(self):
        """run_tui: app_add → Exception → sync still called (line 1580-1581)."""
        result, _, mock_sync = self._run_action("app_add", None, "cmd_app_add", exc=RuntimeError("err"))
        mock_sync.assert_any_call("app-add")

    def test_app_edit_success(self):
        """run_tui: app_edit → cmd_app_edit called → sync app-edit."""
        result, mock_cmd, mock_sync = self._run_action("app_edit", "claude", "cmd_app_edit")
        mock_cmd.assert_called_once_with("claude")
        mock_sync.assert_any_call("app-edit")

    def test_app_edit_keyboard_interrupt(self):
        """run_tui: app_edit → KeyboardInterrupt → sync still called (line 1589-1590)."""
        result, _, mock_sync = self._run_action("app_edit", "claude", "cmd_app_edit", exc=KeyboardInterrupt)
        mock_sync.assert_any_call("app-edit")

    def test_app_remove_success(self):
        """run_tui: app_remove → cmd_app_remove called → sync app-remove."""
        result, mock_cmd, mock_sync = self._run_action("app_remove", "claude", "cmd_app_remove")
        mock_cmd.assert_called_once_with("claude")
        mock_sync.assert_any_call("app-remove")

    def test_app_remove_keyboard_interrupt(self):
        """run_tui: app_remove → KeyboardInterrupt → sync still called (line 1600-1601)."""
        result, _, mock_sync = self._run_action("app_remove", "claude", "cmd_app_remove", exc=KeyboardInterrupt)
        mock_sync.assert_any_call("app-remove")

    def test_app_remove_exception(self):
        """run_tui: app_remove → Exception → sync still called (line 1602-1603)."""
        result, _, mock_sync = self._run_action("app_remove", "claude", "cmd_app_remove", exc=OSError("err"))
        mock_sync.assert_any_call("app-remove")

    def test_app_note_success(self):
        """run_tui: app_note → cmd_app_note called → sync app-note."""
        result, mock_cmd, mock_sync = self._run_action("app_note", "claude", "cmd_app_note")
        mock_cmd.assert_called_once_with("claude")
        mock_sync.assert_any_call("app-note")

    def test_app_note_keyboard_interrupt(self):
        """run_tui: app_note → KeyboardInterrupt → sync still called (line 1611-1612)."""
        result, _, mock_sync = self._run_action("app_note", "claude", "cmd_app_note", exc=KeyboardInterrupt)
        mock_sync.assert_any_call("app-note")

    def test_app_note_exception(self):
        """run_tui: app_note → Exception → sync still called (line 1613-1614)."""
        result, _, mock_sync = self._run_action("app_note", "claude", "cmd_app_note", exc=ValueError("err"))
        mock_sync.assert_any_call("app-note")


@unittest.skipUnless(HAS_TEXTUAL, "textual not installed")
class TestRunTuiEnvEdit(unittest.TestCase):
    """Tests for 'env_edit' action (lines 1666-1685).

    find_environment and update_environment are local imports inside run_tui(),
    so they must be patched at source module level (nexus.environment).
    """

    def test_env_edit_not_found(self):
        """run_tui: env_edit → find_environment returns None → prints not found."""
        FakeApp = _make_app_class([("env_edit", "mymachine"), None])
        with patch("nexus.tui.app.NexusApp", FakeApp), \
             patch("nexus.environment.find_environment", return_value=None), \
             patch("builtins.print") as mock_print:
            result = run_tui()
        self.assertEqual(result, 0)
        printed = " ".join(str(c) for c in mock_print.call_args_list)
        self.assertIn("não encontrado", printed)

    def test_env_edit_found_updates(self):
        """run_tui: env_edit → found → user updates name/location → update_environment called."""
        FakeApp = _make_app_class([("env_edit", "mymachine"), None])
        env = MagicMock()
        env.name = "OldName"
        env.hostname = "mymachine"
        env.location = "Home"
        with patch("nexus.tui.app.NexusApp", FakeApp), \
             patch("nexus.environment.find_environment", return_value=env), \
             patch("builtins.input", side_effect=["NewName", "Work"]), \
             patch("nexus.environment.update_environment") as mock_update, \
             patch("nexus.tui.app._tui_sync_background") as mock_sync:
            result = run_tui()
        self.assertEqual(result, 0)
        mock_update.assert_called_once_with("mymachine", name="NewName", location="Work")
        mock_sync.assert_any_call("env-edit")

    def test_env_edit_found_empty_input_keeps_original(self):
        """run_tui: env_edit → found → empty input → keeps original name/location."""
        FakeApp = _make_app_class([("env_edit", "mymachine"), None])
        env = MagicMock()
        env.name = "OldName"
        env.hostname = "mymachine"
        env.location = "Home"
        with patch("nexus.tui.app.NexusApp", FakeApp), \
             patch("nexus.environment.find_environment", return_value=env), \
             patch("builtins.input", side_effect=["", ""]), \
             patch("nexus.environment.update_environment") as mock_update, \
             patch("nexus.tui.app._tui_sync_background"):
            result = run_tui()
        mock_update.assert_called_once_with("mymachine", name="OldName", location="Home")

    def test_env_edit_keyboard_interrupt_continues(self):
        """run_tui: env_edit → KeyboardInterrupt on input → continue loop (line 1678-1681)."""
        FakeApp = _make_app_class([("env_edit", "mymachine"), None])
        env = MagicMock()
        env.name = "OldName"
        env.hostname = "mymachine"
        env.location = "Home"
        with patch("nexus.tui.app.NexusApp", FakeApp), \
             patch("nexus.environment.find_environment", return_value=env), \
             patch("builtins.input", side_effect=KeyboardInterrupt), \
             patch("nexus.environment.update_environment") as mock_update:
            result = run_tui()
        self.assertEqual(result, 0)
        mock_update.assert_not_called()


@unittest.skipUnless(HAS_TEXTUAL, "textual not installed")
class TestRunTuiInitialTab(unittest.TestCase):
    """Test that initial_tab argument is passed to NexusApp."""

    def test_run_tui_passes_initial_tab(self):
        """run_tui: initial_tab 'projects' → NexusApp gets initial_tab='projects'."""
        created_tabs = []

        class FakeApp:
            def __init__(self, initial_tab="ideas"):
                created_tabs.append(initial_tab)

            def run(self):
                return None  # Immediately exit

        with patch("nexus.tui.app.NexusApp", FakeApp):
            result = run_tui(initial_tab="projects")
        self.assertEqual(result, 0)
        self.assertEqual(created_tabs[0], "projects")
