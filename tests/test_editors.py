import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from nexus.editors import (
    EditorConfig, load_editors, save_editors, get_default_editor, open_in_editor,
    is_windows_path, is_wsl_windows_path, normalize_editor_path, add_editor,
)


class TestEditors(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.config_path = Path(self.tmpdir.name) / "local.yml"
        self.patches = [
            patch("nexus.local_config.LOCAL_CONFIG_PATH", self.config_path),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.tmpdir.cleanup()

    def test_load_empty(self):
        editors, default = load_editors()
        self.assertEqual(editors, [])
        self.assertEqual(default, "")

    def test_save_and_load_round_trip(self):
        editors = [
            EditorConfig(name="vim", command="vim", type="terminal"),
            EditorConfig(name="typora", command="/mnt/c/Typora/Typora.exe", type="gui-windows"),
        ]
        save_editors(editors, "vim")
        loaded_editors, default = load_editors()
        self.assertEqual(len(loaded_editors), 2)
        self.assertEqual(loaded_editors[0].name, "vim")
        self.assertEqual(loaded_editors[0].type, "terminal")
        self.assertEqual(loaded_editors[1].name, "typora")
        self.assertEqual(loaded_editors[1].type, "gui-windows")
        self.assertEqual(default, "vim")

    def test_get_default_editor_returns_matching(self):
        editors = [
            EditorConfig(name="vim", command="vim"),
            EditorConfig(name="code", command="code"),
        ]
        save_editors(editors, "code")
        result = get_default_editor()
        self.assertIsNotNone(result)
        self.assertEqual(result.name, "code")

    def test_get_default_editor_falls_back_to_first(self):
        editors = [EditorConfig(name="vim", command="vim")]
        save_editors(editors, "nonexistent")
        result = get_default_editor()
        self.assertEqual(result.name, "vim")

    def test_get_default_editor_empty(self):
        result = get_default_editor()
        self.assertIsNone(result)

    def test_save_preserves_other_config(self):
        # Write config with path overrides first
        import yaml
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        config = {"path_overrides": {"/old": "/new"}}
        self.config_path.write_text(yaml.dump(config))

        editors = [EditorConfig(name="vim", command="vim")]
        save_editors(editors, "vim")

        loaded = yaml.safe_load(self.config_path.read_text())
        self.assertIn("path_overrides", loaded)
        self.assertEqual(loaded["path_overrides"]["/old"], "/new")
        self.assertIn("editors", loaded)

    @patch("nexus.editors.subprocess.run")
    def test_open_in_editor_terminal(self, mock_run):
        editor = EditorConfig(name="vim", command="vim", type="terminal")
        open_in_editor(editor, "/tmp/test.md")
        mock_run.assert_called_once_with(["vim", "/tmp/test.md"])

    @patch("nexus.editors.subprocess.Popen")
    def test_open_in_editor_gui(self, mock_popen):
        editor = EditorConfig(name="code", command="code", type="gui")
        open_in_editor(editor, "/tmp/test.md")
        mock_popen.assert_called_once_with(["code", "/tmp/test.md"])

    @patch("nexus.editors.subprocess.Popen")
    @patch("nexus.editors.subprocess.run")
    def test_open_in_editor_gui_windows(self, mock_run, mock_popen):
        """gui-windows: normalizes command to WSL, converts file to Windows, Popen."""
        mock_run.return_value = MagicMock(returncode=0, stdout="C:\\tmp\\test.md\n")
        editor = EditorConfig(name="typora", command="/mnt/c/Typora/Typora.exe", type="gui-windows")
        open_in_editor(editor, "/tmp/test.md")
        # File converted to Windows path, command kept as WSL path
        mock_popen.assert_called_once_with(["/mnt/c/Typora/Typora.exe", "C:\\tmp\\test.md"])


class TestOpenEditorGuiWindowsLegacy(unittest.TestCase):
    """gui-windows editors with legacy Windows-path commands."""

    @patch("nexus.editors.subprocess.Popen")
    @patch("nexus.editors.subprocess.run")
    def test_legacy_windows_command_normalized_to_wsl(self, mock_run, mock_popen):
        """Editor stored with C:\\ command: normalized to WSL for execution."""
        def run_side_effect(args, **kwargs):
            if args[0] == "wslpath" and args[1] == "-u":
                return MagicMock(returncode=0, stdout="/mnt/c/Typora/Typora.exe\n")
            if args[0] == "wslpath" and args[1] == "-w":
                return MagicMock(returncode=0, stdout="C:\\tmp\\test.md\n")
            return MagicMock(returncode=0, stdout="")
        mock_run.side_effect = run_side_effect
        editor = EditorConfig(name="typora", command=r"C:\Typora\Typora.exe", type="gui-windows")
        open_in_editor(editor, "/tmp/test.md")
        mock_popen.assert_called_once_with(["/mnt/c/Typora/Typora.exe", "C:\\tmp\\test.md"])


class TestEditorPathDetection(unittest.TestCase):
    """Tests for is_windows_path() and is_wsl_windows_path()."""

    def test_windows_path_backslash(self):
        self.assertTrue(is_windows_path(r"C:\Program Files\Typora\Typora.exe"))

    def test_windows_path_forward_slash(self):
        self.assertTrue(is_windows_path("C:/Program Files/Typora/Typora.exe"))

    def test_windows_path_lowercase_drive(self):
        self.assertTrue(is_windows_path(r"d:\apps\editor.exe"))

    def test_not_windows_wsl_mount(self):
        self.assertFalse(is_windows_path("/mnt/c/Program Files/Typora/Typora.exe"))

    def test_not_windows_simple_command(self):
        self.assertFalse(is_windows_path("vim"))

    def test_not_windows_linux_path(self):
        self.assertFalse(is_windows_path("/usr/bin/vim"))

    def test_not_windows_empty(self):
        self.assertFalse(is_windows_path(""))

    def test_wsl_mount_path(self):
        self.assertTrue(is_wsl_windows_path("/mnt/c/Program Files/Typora/Typora.exe"))

    def test_wsl_mount_path_other_drive(self):
        self.assertTrue(is_wsl_windows_path("/mnt/d/apps/editor.exe"))

    def test_not_wsl_mount_linux(self):
        self.assertFalse(is_wsl_windows_path("/usr/bin/vim"))

    def test_not_wsl_mount_simple(self):
        self.assertFalse(is_wsl_windows_path("vim"))

    def test_not_wsl_mount_windows(self):
        self.assertFalse(is_wsl_windows_path(r"C:\test"))


class TestNormalizeEditorPath(unittest.TestCase):
    """Tests for normalize_editor_path()."""

    @patch("nexus.editors.subprocess.run")
    def test_converts_windows_path(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="/mnt/c/Program Files/Typora/Typora.exe\n"
        )
        result = normalize_editor_path(r"C:\Program Files\Typora\Typora.exe")
        self.assertEqual(result, "/mnt/c/Program Files/Typora/Typora.exe")
        mock_run.assert_called_once_with(
            ["wslpath", "-u", r"C:\Program Files\Typora\Typora.exe"],
            capture_output=True, text=True,
        )

    def test_keeps_wsl_path(self):
        result = normalize_editor_path("/mnt/c/Program Files/Typora/Typora.exe")
        self.assertEqual(result, "/mnt/c/Program Files/Typora/Typora.exe")

    def test_keeps_simple_command(self):
        result = normalize_editor_path("vim")
        self.assertEqual(result, "vim")

    def test_keeps_linux_path(self):
        result = normalize_editor_path("/usr/bin/vim")
        self.assertEqual(result, "/usr/bin/vim")

    @patch("nexus.editors.subprocess.run")
    def test_fallback_on_wslpath_failure(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="")
        result = normalize_editor_path(r"C:\bad\path.exe")
        self.assertEqual(result, r"C:\bad\path.exe")


class TestAddEditorPathHandling(unittest.TestCase):
    """Tests for add_editor() integration with path normalization."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.config_path = Path(self.tmpdir.name) / "local.yml"
        # Create empty config so load_local_config doesn't fail
        self.config_path.write_text("{}", encoding="utf-8")
        self.patches = [
            patch("nexus.local_config.LOCAL_CONFIG_PATH", self.config_path),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.tmpdir.cleanup()

    @patch("nexus.editors.Path.exists", return_value=True)
    @patch("nexus.editors.subprocess.run")
    @patch("builtins.input")
    def test_windows_path_auto_converts_and_detects_type(self, mock_input, mock_run, _mock_exists):
        """C:\\ path -> converted to WSL, type auto-detected as gui-windows."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="/mnt/c/Program Files/Typora/Typora.exe\n"
        )
        mock_input.side_effect = ["typora", r"C:\Program Files\Typora\Typora.exe", ""]
        editor = add_editor()
        self.assertIsNotNone(editor)
        self.assertEqual(editor.command, "/mnt/c/Program Files/Typora/Typora.exe")
        self.assertEqual(editor.type, "gui-windows")

    @patch("nexus.editors.Path.exists", return_value=True)
    @patch("builtins.input")
    def test_wsl_mount_path_auto_detects_type(self, mock_input, _mock_exists):
        """/mnt/c/ path -> no conversion needed, type auto-detected as gui-windows."""
        mock_input.side_effect = ["typora", "/mnt/c/Program Files/Typora/Typora.exe", ""]
        editor = add_editor()
        self.assertIsNotNone(editor)
        self.assertEqual(editor.command, "/mnt/c/Program Files/Typora/Typora.exe")
        self.assertEqual(editor.type, "gui-windows")

    @patch("builtins.input")
    def test_simple_command_no_conversion(self, mock_input):
        """Simple command -> no conversion, manual type selection."""
        mock_input.side_effect = ["vim", "vim", "1"]
        editor = add_editor()
        self.assertIsNotNone(editor)
        self.assertEqual(editor.command, "vim")
        self.assertEqual(editor.type, "terminal")

    @patch("nexus.editors.Path.exists", return_value=True)
    @patch("builtins.input")
    def test_linux_path_no_auto_detect(self, mock_input, _mock_exists):
        """/usr/bin/ path -> no conversion, manual type selection."""
        mock_input.side_effect = ["code", "/usr/bin/code", "2"]
        editor = add_editor()
        self.assertIsNotNone(editor)
        self.assertEqual(editor.command, "/usr/bin/code")
        self.assertEqual(editor.type, "gui")

    @patch("nexus.editors.Path.exists", return_value=False)
    @patch("builtins.input")
    def test_nonexistent_path_warns_and_cancels(self, mock_input, _mock_exists):
        """Path that doesn't exist shows warning, user can cancel."""
        mock_input.side_effect = ["typora", "/mnt/c/bad/path.exe", "n"]
        editor = add_editor()
        self.assertIsNone(editor)

    @patch("nexus.editors.Path.exists", return_value=False)
    @patch("builtins.input")
    def test_nonexistent_path_warns_but_user_proceeds(self, mock_input, _mock_exists):
        """Path that doesn't exist shows warning, user can proceed anyway."""
        mock_input.side_effect = ["typora", "/mnt/c/bad/path.exe", "s", ""]
        editor = add_editor()
        self.assertIsNotNone(editor)
        self.assertEqual(editor.command, "/mnt/c/bad/path.exe")


if __name__ == "__main__":
    unittest.main()
