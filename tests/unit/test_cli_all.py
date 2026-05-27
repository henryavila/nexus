from typer.testing import CliRunner
from nexus.cli import app

runner = CliRunner()


def test_idea_add(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_DATA_DIR", str(tmp_path))
    result = runner.invoke(app, ["idea", "add", "Cool Idea"])
    assert result.exit_code == 0
    assert "Cool Idea" in result.stdout


def test_idea_list(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_DATA_DIR", str(tmp_path))
    result = runner.invoke(app, ["idea", "list"])
    assert result.exit_code == 0


def test_app_add(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_DATA_DIR", str(tmp_path))
    result = runner.invoke(app, ["app", "add", "My App"])
    assert result.exit_code == 0


def test_codex_add(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_DATA_DIR", str(tmp_path))
    result = runner.invoke(app, ["codex", "add", "My Guide", "--kind", "guia"])
    assert result.exit_code == 0


def test_skill_add(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_DATA_DIR", str(tmp_path))
    result = runner.invoke(app, ["skill", "add", "TDD"])
    assert result.exit_code == 0


def test_env_list(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_DATA_DIR", str(tmp_path))
    result = runner.invoke(app, ["env", "list"])
    assert result.exit_code == 0


def test_tui_command_exists(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_DATA_DIR", str(tmp_path))
    result = runner.invoke(app, ["tui", "--help"])
    assert result.exit_code == 0
