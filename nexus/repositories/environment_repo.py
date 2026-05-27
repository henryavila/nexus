from __future__ import annotations
from nexus.config import NexusConfig
from nexus.models import Environment
from .base import YamlRepository


class EnvironmentRepository(YamlRepository[Environment]):
    def __init__(self, config: NexusConfig):
        super().__init__(
            path=config.environments_yml,
            model=Environment,
            collection_key="environments",
            id_field="hostname",
        )

    def find_by_hostname(self, hostname: str) -> Environment | None:
        return self.get(hostname)
