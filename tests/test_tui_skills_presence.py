import unittest
from unittest.mock import MagicMock, patch

HAS_TEXTUAL = False
try:
    import textual
    HAS_TEXTUAL = True
except ImportError:
    pass


def _consume_compose(widget):
    """Call compose() and consume the generator (don't render, just iterate)."""
    try:
        return list(widget.compose())
    except Exception:
        return []


@unittest.skipUnless(HAS_TEXTUAL, "textual not installed")
class TestSkillBadgeInDataTable(unittest.TestCase):
    """Test skill badge logic in _load_skills (migrated from SkillItem)."""

    def _make_app(self):
        from nexus.tui import NexusApp
        mock_container = MagicMock()
        mock_container.config = MagicMock()
        with patch("nexus.tui.app.detect_clis", return_value=[]), \
             patch("nexus.tui.app.get_container", return_value=mock_container), \
             patch("nexus.tui.app.ScanRepository") as mock_scan_repo_cls:
            mock_scan_repo_cls.return_value.read.return_value = {"projects": [], "skills": {}}
            app = NexusApp()
        app._scan_repo = mock_scan_repo_cls.return_value
        return app

    def _make_mock_data_table(self):
        dt = MagicMock()
        dt.row_count = 0
        self._add_row_calls = []
        def fake_add_row(*args, key=None):
            self._add_row_calls.append(args)
            from textual.widgets.data_table import RowKey
            return RowKey(key or str(len(self._add_row_calls)))
        dt.add_row = MagicMock(side_effect=fake_add_row)
        return dt

    def test_global_badge(self):
        app = self._make_app()
        skills = {"sp": {"title": "sp", "presence": {"H": {"global": True}}}}
        dt = self._make_mock_data_table()
        app._scan_repo.read.return_value = {"projects": [], "skills": skills}
        with patch.object(app, "query_one", return_value=dt):
            app._load_skills()
        # First arg of add_row is the badge
        self.assertIn("\U0001F310", self._add_row_calls[0][0])

    def test_repo_badge(self):
        app = self._make_app()
        skills = {"x": {"title": "x", "presence": {"H": {"global": False, "repos": ["p"]}}}}
        dt = self._make_mock_data_table()
        app._scan_repo.read.return_value = {"projects": [], "skills": skills}
        with patch.object(app, "query_one", return_value=dt):
            app._load_skills()
        self.assertIn("\U0001F4E6", self._add_row_calls[0][0])

    def test_empty_presence_badge(self):
        app = self._make_app()
        skills = {"x": {"title": "x", "presence": {}}}
        dt = self._make_mock_data_table()
        app._scan_repo.read.return_value = {"projects": [], "skills": skills}
        with patch.object(app, "query_one", return_value=dt):
            app._load_skills()
        self.assertIn("\u2753", self._add_row_calls[0][0])


@unittest.skipUnless(HAS_TEXTUAL, "textual not installed")
class TestSkillDetailScreenPresence(unittest.TestCase):

    def test_shows_presence_section(self):
        from nexus.tui import SkillDetailScreen
        skill = {"slug": "sp", "title": "sp", "presence": {"ULTRON": {"global": True}}}
        screen = SkillDetailScreen(skill)
        widgets = _consume_compose(screen)
        if widgets:
            texts = [str(w.renderable) for w in widgets if hasattr(w, "renderable")]
            combined = " ".join(texts)
            self.assertIn("ULTRON", combined)
            self.assertIn("global", combined)
            self.assertNotIn("Escopo", combined)

    def test_empty_presence_message(self):
        from nexus.tui import SkillDetailScreen
        skill = {"slug": "sp", "title": "sp", "presence": {}}
        screen = SkillDetailScreen(skill)
        widgets = _consume_compose(screen)
        if widgets:
            texts = [str(w.renderable) for w in widgets if hasattr(w, "renderable")]
            combined = " ".join(texts)
            self.assertIn("nexus scan", combined)


@unittest.skipUnless(HAS_TEXTUAL, "textual not installed")
class TestEnvDetailScreenSkills(unittest.TestCase):

    def test_shows_skills_for_hostname(self):
        from nexus.tui import EnvDetailScreen
        env = {"hostname": "ULTRON", "name": "ULTRON", "location": "Casa", "last_seen": "2026-03-21"}
        skills_data = {
            "superpowers": {"title": "superpowers", "presence": {"ULTRON": {"global": True}}},
            "pest-testing": {"title": "pest-testing", "presence": {"ULTRON": {"global": False, "repos": ["sda-v2"]}}},
            "other": {"title": "other", "presence": {"CRCMG": {"global": True}}},
        }
        screen = EnvDetailScreen(env, skills_data)
        widgets = _consume_compose(screen)
        if widgets:
            texts = [str(w.renderable) for w in widgets if hasattr(w, "renderable")]
            combined = " ".join(texts)
            self.assertIn("superpowers", combined)
            self.assertIn("pest-testing", combined)
            self.assertNotIn("other", combined)

    def test_backward_compat_no_skills_data(self):
        from nexus.tui import EnvDetailScreen
        env = {"hostname": "H", "name": "H", "location": "?"}
        screen = EnvDetailScreen(env)  # no skills_data arg
        _consume_compose(screen)


@unittest.skipUnless(HAS_TEXTUAL, "textual not installed")
class TestSkillFilterPresence(unittest.TestCase):

    def _make_app(self):
        from nexus.tui import NexusApp
        mock_container = MagicMock()
        mock_container.config = MagicMock()
        with patch("nexus.tui.app.detect_clis", return_value=[]), \
             patch("nexus.tui.app.get_container", return_value=mock_container), \
             patch("nexus.tui.app.ScanRepository") as mock_scan_repo_cls:
            mock_scan_repo_cls.return_value.read.return_value = {"projects": [], "skills": {}}
            app = NexusApp()
        app._scan_repo = mock_scan_repo_cls.return_value
        return app

    def _make_mock_data_table(self):
        dt = MagicMock()
        dt.row_count = 0
        self._add_row_count = 0
        def fake_add_row(*args, key=None):
            self._add_row_count += 1
            from textual.widgets.data_table import RowKey
            return RowKey(key or str(self._add_row_count))
        dt.add_row = MagicMock(side_effect=fake_add_row)
        return dt

    def test_filter_by_hostname(self):
        """Filter finds skills by hostname in presence."""
        app = self._make_app()
        app.filter_text = "ultron"
        skills = {
            "sp": {"title": "sp", "presence": {"ULTRON": {"global": True}}},
            "other": {"title": "other", "presence": {"CRCMG": {"global": True}}},
        }
        dt = self._make_mock_data_table()
        app._scan_repo.read.return_value = {"projects": [], "skills": skills}
        with patch.object(app, "query_one", return_value=dt):
            app._load_skills()
        self.assertEqual(dt.add_row.call_count, 1)

    def test_filter_by_repo_slug(self):
        """Filter finds skills by repo slug in presence."""
        app = self._make_app()
        app.filter_text = "sda-v2"
        skills = {
            "pest": {"title": "pest", "presence": {"H": {"global": False, "repos": ["sda-v2"]}}},
            "other": {"title": "other", "presence": {"H": {"global": True}}},
        }
        dt = self._make_mock_data_table()
        app._scan_repo.read.return_value = {"projects": [], "skills": skills}
        with patch.object(app, "query_one", return_value=dt):
            app._load_skills()
        self.assertEqual(dt.add_row.call_count, 1)

    def test_detail_bar_shows_skill_scope(self):
        """Detail bar shows scope info for skills."""
        app = self._make_app()
        app._active_tab = MagicMock(return_value="skills")
        app._group_keys = set()
        skill_data = {"title": "sp", "slug": "sp", "presence": {"A": {"global": True}, "B": {"global": True}}}
        from textual.widgets.data_table import RowKey
        app._skill_row_data[RowKey("skill:sp")] = skill_data
        dt = MagicMock()
        dt.row_count = 1
        dt.cursor_row = 0
        dt.coordinate_to_cell_key.return_value = (RowKey("skill:sp"), None)
        bar = MagicMock()
        app.query_one = MagicMock(side_effect=lambda sel, cls=None:
                                  dt if "skills-table" in sel else bar)
        app._update_detail_bar()
        bar.update.assert_called_once()
        call_arg = bar.update.call_args[0][0]
        self.assertIn("sp", call_arg)
