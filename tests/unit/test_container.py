from nexus.config import NexusConfig
from nexus.services import ServiceContainer


def test_container_creates_all_services(tmp_path):
    cfg = NexusConfig(data_dir=tmp_path)
    cfg.ensure_dirs()
    container = ServiceContainer(cfg)
    assert container.projects is not None
    assert container.apps is not None
    assert container.ideas is not None
    assert container.codex is not None
    assert container.environments is not None
    assert container.sync is not None


def test_container_services_share_sync(tmp_path):
    cfg = NexusConfig(data_dir=tmp_path)
    cfg.ensure_dirs()
    container = ServiceContainer(cfg)
    assert container.projects._sync is container.sync
    assert container.apps._sync is container.sync
