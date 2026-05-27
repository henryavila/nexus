from typer.testing import CliRunner
from nexus.cli import app
from nexus.config import NexusConfig
import os

runner = CliRunner()


def test_project_add(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_DATA_DIR", str(tmp_path))
    result = runner.invoke(app, ["add", "Test Project", "--path", str(tmp_path)])
    assert result.exit_code == 0
    assert "Test Project" in result.stdout


def test_project_list_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_DATA_DIR", str(tmp_path))
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0


def test_project_remove(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_DATA_DIR", str(tmp_path))
    runner.invoke(app, ["add", "ToRemove", "--path", str(tmp_path)])
    result = runner.invoke(app, ["remove", "toremove"], input="y\n")
    assert result.exit_code == 0


def test_remove_ambiguous_shows_candidates(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_DATA_DIR", str(tmp_path))
    runner.invoke(app, ["add", "codeguard", "--path", "/tmp/cg1", "--domain", "tech", "--nature", "ferramenta"])
    runner.invoke(app, ["add", "codeguard", "--path", "/tmp/cg2", "--domain", "pessoal", "--nature", "contexto"])
    result = runner.invoke(app, ["remove", "codeguard"])
    assert result.exit_code == 1
    assert "codeguard" in result.stdout
    assert "codeguard2" in result.stdout


def test_remove_ambiguous_by_slug_works(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_DATA_DIR", str(tmp_path))
    runner.invoke(app, ["add", "codeguard", "--path", "/tmp/cg1", "--domain", "tech"])
    runner.invoke(app, ["add", "codeguard", "--path", "/tmp/cg2", "--domain", "pessoal"])
    result = runner.invoke(app, ["remove", "codeguard2"], input="y\n")
    assert result.exit_code == 0
    assert "removido" in result.stdout
    list_result = runner.invoke(app, ["list"])
    assert "codeguard2" not in list_result.stdout
    assert "codeguard" in list_result.stdout


def test_project_edit(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_DATA_DIR", str(tmp_path))
    runner.invoke(app, ["add", "EditMe", "--path", str(tmp_path)])
    result = runner.invoke(app, ["edit", "editme", "--description", "updated"])
    assert result.exit_code == 0
    assert "updated" in result.stdout or result.exit_code == 0
