import pytest
from pathlib import Path
from unittest.mock import patch


@pytest.fixture
def nexus_env(tmp_path):
    """Full isolated nexus environment with all paths patched."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    projects_yml = data_dir / "projects.yml"
    ideas_yml = data_dir / "ideas.yml"
    apps_yml = data_dir / "apps.yml"
    env_yml = data_dir / "environments.yml"
    codex_dir = data_dir / "codex"
    data_json = tmp_path / "data.json"
    lock_file = tmp_path / ".nexus.lock"
    local_config_path = tmp_path / "local.yml"

    patches = [
        # Module-level constants (where each module imports from __init__)
        patch("nexus.registry.PROJECTS_YML", projects_yml),
        patch("nexus.registry.DATA_JSON", data_json),
        patch("nexus.registry.DATA_DIR", data_dir),
        patch("nexus.ideas.IDEAS_YML", ideas_yml),
        patch("nexus.ideas.DATA_JSON", data_json),
        patch("nexus.ideas.LOCK_FILE", lock_file),
        patch("nexus.apps.APPS_YML", apps_yml),
        patch("nexus.apps.DATA_JSON", data_json),
        patch("nexus.apps.LOCK_FILE", lock_file),
        patch("nexus.codex.CODEX_DIR", codex_dir),
        patch("nexus.codex.DATA_JSON", data_json),
        patch("nexus.codex.LOCK_FILE", lock_file),
        patch("nexus.scanner.DATA_JSON", data_json),
        patch("nexus.scanner.LOCK_FILE", lock_file),
        patch("nexus.environment.ENVIRONMENTS_YML", env_yml),
        # __init__ module constants (used by cmd_* via `from . import X`)
        patch("nexus.DATA_JSON", data_json),
        patch("nexus.LOCK_FILE", lock_file),
        patch("nexus.APPS_YML", apps_yml),
        patch("nexus.IDEAS_YML", ideas_yml),
        patch("nexus.ENVIRONMENTS_YML", env_yml),
        patch("nexus.PROJECTS_YML", projects_yml),
        patch("nexus.DATA_DIR", data_dir),
        # Local config (editors read/write ~/.config/nexus/local.yml)
        patch("nexus.local_config.LOCAL_CONFIG_PATH", local_config_path),
        # Isolate from real ~/.claude/settings.json
    ]
    for p in patches:
        p.start()

    # Make dirs that code expects to exist
    codex_dir.mkdir(exist_ok=True)

    yield tmp_path

    for p in patches:
        p.stop()


@pytest.fixture
def mock_input():
    """Patch builtins.input with a list of responses."""
    with patch("builtins.input") as mock:
        yield mock


@pytest.fixture
def mock_editor():
    """Patch editor functions to avoid opening real editors."""
    from nexus.editors import EditorConfig
    editor = EditorConfig(command="cat", type="terminal", name="cat")
    with patch("nexus._legacy_main.get_default_editor", return_value=editor), \
         patch("nexus._legacy_main.open_in_editor"), \
         patch("nexus._legacy_main.editor_add", return_value=editor):
        yield editor
