from typer.testing import CliRunner
from nexus.cli import app
from pathlib import Path

runner = CliRunner()


def test_init_creates_data_dir(tmp_path, monkeypatch):
    data_dir = tmp_path / "nexus-data"
    monkeypatch.setenv("NEXUS_DATA_DIR", str(data_dir))
    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0
    assert data_dir.exists()
    assert (data_dir / "projects.yml").exists()
    assert (data_dir / "codex").is_dir()


def test_init_with_custom_path(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_DATA_DIR", str(tmp_path / "default"))
    fake_config = tmp_path / "config" / "local.yml"
    monkeypatch.setattr("nexus.config._DEFAULT_CONFIG_PATH", fake_config)
    custom = tmp_path / "custom-data"
    result = runner.invoke(app, ["init", "--data-dir", str(custom)])
    assert result.exit_code == 0
    assert custom.exists()
    assert fake_config.exists()


def test_init_idempotent(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_DATA_DIR", str(tmp_path))
    runner.invoke(app, ["init"])
    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0
