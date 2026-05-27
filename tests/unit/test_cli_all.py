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


# --- App disambiguation ---

def test_app_remove_ambiguous(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_DATA_DIR", str(tmp_path))
    runner.invoke(app, ["app", "add", "MyApp", "--domain", "tech"])
    runner.invoke(app, ["app", "add", "MyApp", "--domain", "pessoal"])
    result = runner.invoke(app, ["app", "remove", "MyApp"])
    assert result.exit_code == 1
    assert "Múltiplos" in result.stdout


def test_app_edit_ambiguous(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_DATA_DIR", str(tmp_path))
    runner.invoke(app, ["app", "add", "MyApp", "--domain", "tech"])
    runner.invoke(app, ["app", "add", "MyApp", "--domain", "pessoal"])
    result = runner.invoke(app, ["app", "edit", "MyApp", "--description", "x"])
    assert result.exit_code == 1
    assert "Múltiplos" in result.stdout


def test_app_edit_by_slug(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_DATA_DIR", str(tmp_path))
    runner.invoke(app, ["app", "add", "MyApp"])
    result = runner.invoke(app, ["app", "edit", "myapp", "--description", "updated"])
    assert result.exit_code == 0
    assert "atualizado" in result.stdout


def test_app_remove_by_slug(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_DATA_DIR", str(tmp_path))
    runner.invoke(app, ["app", "add", "MyApp", "--domain", "tech"])
    runner.invoke(app, ["app", "add", "MyApp", "--domain", "pessoal"])
    result = runner.invoke(app, ["app", "remove", "myapp2"], input="y\n")
    assert result.exit_code == 0
    assert "removido" in result.stdout


# --- Idea disambiguation ---

def test_idea_remove_ambiguous(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_DATA_DIR", str(tmp_path))
    runner.invoke(app, ["idea", "add", "Cool Idea", "--domain", "tech"])
    runner.invoke(app, ["idea", "add", "Cool Idea", "--domain", "pessoal"])
    result = runner.invoke(app, ["idea", "remove", "Cool Idea"])
    assert result.exit_code == 1
    assert "Múltiplos" in result.stdout


def test_idea_edit_ambiguous(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_DATA_DIR", str(tmp_path))
    runner.invoke(app, ["idea", "add", "Cool Idea", "--domain", "tech"])
    runner.invoke(app, ["idea", "add", "Cool Idea", "--domain", "pessoal"])
    result = runner.invoke(app, ["idea", "edit", "Cool Idea", "--priority", "high"])
    assert result.exit_code == 1
    assert "Múltiplos" in result.stdout


def test_idea_edit_by_id(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_DATA_DIR", str(tmp_path))
    runner.invoke(app, ["idea", "add", "Cool Idea"])
    list_result = runner.invoke(app, ["idea", "list"])
    import re
    match = re.search(r'\[(\w+)\]', list_result.stdout)
    idea_id = match.group(1)
    result = runner.invoke(app, ["idea", "edit", idea_id, "--priority", "high"])
    assert result.exit_code == 0
    assert "atualizada" in result.stdout


# --- Codex disambiguation ---

def test_codex_remove_not_found(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_DATA_DIR", str(tmp_path))
    result = runner.invoke(app, ["codex", "remove", "nonexistent"])
    assert result.exit_code == 1


def test_codex_edit(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_DATA_DIR", str(tmp_path))
    runner.invoke(app, ["codex", "add", "My Guide", "--kind", "guia"])
    result = runner.invoke(app, ["codex", "edit", "my-guide", "--kind", "referência"])
    assert result.exit_code == 0
    assert "atualizada" in result.stdout


def test_codex_edit_not_found(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_DATA_DIR", str(tmp_path))
    result = runner.invoke(app, ["codex", "edit", "nonexistent", "--kind", "x"])
    assert result.exit_code == 1


# --- Skill disambiguation ---

def test_skill_remove_not_found(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_DATA_DIR", str(tmp_path))
    result = runner.invoke(app, ["skill", "remove", "nonexistent"])
    assert result.exit_code == 1


def test_skill_edit(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_DATA_DIR", str(tmp_path))
    runner.invoke(app, ["skill", "add", "TDD"])
    result = runner.invoke(app, ["skill", "edit", "tdd", "--scope", "project"])
    assert result.exit_code == 0
    assert "atualizada" in result.stdout


def test_skill_edit_not_found(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_DATA_DIR", str(tmp_path))
    result = runner.invoke(app, ["skill", "edit", "nonexistent", "--scope", "x"])
    assert result.exit_code == 1


# --- Project edit/note disambiguation ---

def test_project_edit_ambiguous(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_DATA_DIR", str(tmp_path))
    runner.invoke(app, ["add", "codeguard", "--path", "/tmp/cg1", "--domain", "tech"])
    runner.invoke(app, ["add", "codeguard", "--path", "/tmp/cg2", "--domain", "pessoal"])
    result = runner.invoke(app, ["edit", "codeguard", "--description", "x"])
    assert result.exit_code == 1
    assert "Múltiplos" in result.stdout


def test_project_note_ambiguous(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_DATA_DIR", str(tmp_path))
    runner.invoke(app, ["add", "codeguard", "--path", "/tmp/cg1", "--domain", "tech"])
    runner.invoke(app, ["add", "codeguard", "--path", "/tmp/cg2", "--domain", "pessoal"])
    result = runner.invoke(app, ["note", "codeguard", "my note"])
    assert result.exit_code == 1
    assert "Múltiplos" in result.stdout


def test_tui_command_exists(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_DATA_DIR", str(tmp_path))
    result = runner.invoke(app, ["tui", "--help"])
    assert result.exit_code == 0
