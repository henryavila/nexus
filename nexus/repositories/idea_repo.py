from __future__ import annotations
import uuid
from nexus.config import NexusConfig
from nexus.models import Idea
from .base import YamlRepository


class IdeaRepository(YamlRepository[Idea]):
    def __init__(self, config: NexusConfig):
        super().__init__(
            path=config.ideas_yml,
            model=Idea,
            collection_key="ideas",
            id_field="id",
        )

    def add(self, item: Idea) -> None:
        if not item.id:
            item.id = uuid.uuid4().hex[:8]
        super().add(item)
