import os
from pathlib import Path
from unittest.mock import patch
import pytest
import yaml
from nexus.config import NexusConfig

LOCAL_CONFIG_PATH = Path.home() / ".config" / "nexus" / "local.yml"


def test_default_data_dir():
    with patch.object(Path, "exists", return_value=False):
        cfg = NexusConfig.load()
    assert cfg.data_dir == Path.home() / ".nexus" / "data"


def test_data_dir_from_local_config(tmp_path):
    custom = tmp_path / "mydata"
    config_file = tmp_path / "local.yml"
    config_file.write_text(yaml.dump({"data_dir": str(custom)}))
    cfg = NexusConfig.load(config_path=config_file)
    assert cfg.data_dir == custom


def test_data_dir_from_env_var(tmp_path, monkeypatch):
    custom = tmp_path / "envdata"
    monkeypatch.setenv("NEXUS_DATA_DIR", str(custom))
    cfg = NexusConfig.load(config_path=tmp_path / "nonexistent.yml")
    assert cfg.data_dir == custom


def test_env_var_overrides_config_file(tmp_path, monkeypatch):
    from_file = tmp_path / "fromfile"
    from_env = tmp_path / "fromenv"
    config_file = tmp_path / "local.yml"
    config_file.write_text(yaml.dump({"data_dir": str(from_file)}))
    monkeypatch.setenv("NEXUS_DATA_DIR", str(from_env))
    cfg = NexusConfig.load(config_path=config_file)
    assert cfg.data_dir == from_env


def test_derived_paths():
    cfg = NexusConfig(data_dir=Path("/tmp/nexus-test"))
    assert cfg.projects_yml == Path("/tmp/nexus-test/projects.yml")
    assert cfg.apps_yml == Path("/tmp/nexus-test/apps.yml")
    assert cfg.ideas_yml == Path("/tmp/nexus-test/ideas.yml")
    assert cfg.environments_yml == Path("/tmp/nexus-test/environments.yml")
    assert cfg.codex_dir == Path("/tmp/nexus-test/codex")
    assert cfg.skills_dir == Path("/tmp/nexus-test/skills")
    assert cfg.data_json == Path("/tmp/nexus-test/data.json")
    assert cfg.lock_file == Path("/tmp/nexus-test/.nexus.lock")


def test_save_local_config(tmp_path):
    config_file = tmp_path / "local.yml"
    cfg = NexusConfig(data_dir=tmp_path / "mydata")
    cfg.save(config_path=config_file)
    loaded = yaml.safe_load(config_file.read_text())
    assert loaded["data_dir"] == str(tmp_path / "mydata")
