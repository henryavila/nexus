from pathlib import Path
from unittest.mock import patch, MagicMock
from nexus.config import NexusConfig
from nexus.services.sync_service import SyncService


def test_quick_sync_calls_git(tmp_path):
    cfg = NexusConfig(data_dir=tmp_path)
    svc = SyncService(cfg, data_repo_path=str(tmp_path))
    with patch("nexus.infra.git_sync.commit_and_push", return_value=True) as mock:
        result = svc.quick_sync(["projects.yml"], "add")
    assert result is True
    mock.assert_called_once()


def test_full_sync(tmp_path):
    cfg = NexusConfig(data_dir=tmp_path)
    svc = SyncService(cfg, data_repo_path=str(tmp_path))
    with patch("nexus.infra.git_sync.commit_and_push", return_value=True) as mock:
        result = svc.full_sync("scan")
    assert result is True


def test_no_sync_without_repo(tmp_path):
    cfg = NexusConfig(data_dir=tmp_path)
    svc = SyncService(cfg, data_repo_path=None)
    result = svc.quick_sync(["projects.yml"], "add")
    assert result is True
