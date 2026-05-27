from __future__ import annotations
from nexus.config import NexusConfig
from nexus.models import Project
from nexus.slug import make_short_slug
from .base import YamlRepository


class ProjectRepository(YamlRepository[Project]):
    def __init__(self, config: NexusConfig):
        super().__init__(
            path=config.projects_yml,
            model=Project,
            collection_key="projects",
            id_field="slug",
        )

    def add(self, item: Project) -> None:
        if not item.slug:
            item.slug = self._unique_slug(item.name)
        super().add(item)

    def _unique_slug(self, name: str) -> str:
        existing = {p.slug for p in self.load_all()}
        base = make_short_slug(name)
        if base not in existing:
            return base
        for i in range(2, 100):
            candidate = f"{base}{i}"
            if candidate not in existing:
                return candidate
        return base

    def resolve_by_path(self, path: str) -> Project | None:
        normalized = path.rstrip("/").lower()
        for p in self.load_all():
            if p.path and p.path.rstrip("/").lower() == normalized:
                return p
        return None
