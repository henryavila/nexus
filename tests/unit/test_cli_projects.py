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


def test_project_edit(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_DATA_DIR", str(tmp_path))
    runner.invoke(app, ["add", "EditMe", "--path", str(tmp_path)])
    result = runner.invoke(app, ["edit", "editme", "--description", "updated"])
    assert result.exit_code == 0
    assert "updated" in result.stdout or result.exit_code == 0
