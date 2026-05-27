from __future__ import annotations
import re
from nexus.config import NexusConfig
from nexus.models import App
from .base import YamlRepository


class AppRepository(YamlRepository[App]):
    def __init__(self, config: NexusConfig):
        super().__init__(
            path=config.apps_yml,
            model=App,
            collection_key="apps",
            id_field="slug",
        )

    def add(self, item: App) -> None:
        if not item.slug:
            item.slug = self._make_slug(item.name)
        super().add(item)

    def _make_slug(self, name: str) -> str:
        s = name.lower().strip()
        s = re.sub(r"[^\w\s-]", "", s)
        s = re.sub(r"[\s_]+", "-", s)
        return s.strip("-")
