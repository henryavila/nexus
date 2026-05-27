import shutil
from pathlib import Path
from typer.testing import CliRunner
from nexus.cli import app

runner = CliRunner()


def test_migrate_copies_files(tmp_path, monkeypatch):
    old_data = tmp_path / "old-repo" / "data"
    old_data.mkdir(parents=True)
    (old_data / "projects.yml").write_text("projects: [{name: Test}]")
    (old_data / "apps.yml").write_text("apps: []")
    (old_data / "ideas.yml").write_text("ideas: []")
    (old_data / "environments.yml").write_text("environments: []")
    codex = old_data / "codex"
    codex.mkdir()
    (codex / "guide.md").write_text("---\ntitle: Guide\n---\nHello")

    new_data = tmp_path / "new-data"
    monkeypatch.setenv("NEXUS_DATA_DIR", str(new_data))
    result = runner.invoke(app, ["migrate", "--from", str(old_data)])
    assert result.exit_code == 0
    assert (new_data / "projects.yml").exists()
    assert (new_data / "codex" / "guide.md").exists()


def test_migrate_refuses_overwrite(tmp_path, monkeypatch):
    new_data = tmp_path / "new-data"
    new_data.mkdir()
    (new_data / "projects.yml").write_text("projects: [{name: Existing}]")
    monkeypatch.setenv("NEXUS_DATA_DIR", str(new_data))
    old = tmp_path / "old" / "data"
    old.mkdir(parents=True)
    (old / "projects.yml").write_text("projects: [{name: Other}]")
    result = runner.invoke(app, ["migrate", "--from", str(old)], input="n\n")
    assert "já existe" in result.stdout or result.exit_code != 0
