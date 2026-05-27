from __future__ import annotations
from nexus.config import NexusConfig
from nexus.services.sync_service import SyncService
from nexus.services.project_service import ProjectService
from nexus.services.app_service import AppService
from nexus.services.idea_service import IdeaService
from nexus.services.codex_service import CodexService
from nexus.services.environment_service import EnvironmentService


class ServiceContainer:
    def __init__(self, config: NexusConfig, data_repo_path: str | None = None):
        self.config = config
        config.ensure_dirs()
        self.sync = SyncService(config, data_repo_path=data_repo_path)
        self.projects = ProjectService(config, self.sync)
        self.apps = AppService(config, self.sync)
        self.ideas = IdeaService(config, self.sync)
        self.codex = CodexService(config, self.sync)
        self.environments = EnvironmentService(config, self.sync)
