from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "frontend" / "index.html"
APP_JS = ROOT / "frontend" / "js" / "app.js"


def test_index_includes_mobile_tab_strip_and_more_menu():
    html = INDEX.read_text(encoding="utf-8")

    assert 'id="primary-tabs"' in html
    assert 'id="more-btn"' in html
    assert 'id="more-menu"' in html


def test_index_includes_shared_detail_overlay():
    html = INDEX.read_text(encoding="utf-8")

    assert 'id="detail-overlay"' in html
    assert 'id="detail-panel"' in html
    assert 'id="detail-body"' in html


def test_app_js_uses_shared_detail_overlay_for_ideas_and_codex():
    js = APP_JS.read_text(encoding="utf-8")

    assert "openDetailOverlay(" in js
    assert "renderIdeas(" in js
    assert "renderCodex(" in js
