from __future__ import annotations
from datetime import date
from nexus.config import NexusConfig
from nexus.models import Project
from nexus.repositories.project_repo import ProjectRepository
from nexus.services.sync_service import SyncService


class ProjectService:
    def __init__(self, config: NexusConfig, sync: SyncService):
        self._repo = ProjectRepository(config)
        self._sync = sync

    def add(self, name: str, path: str | None = None, **kwargs) -> Project:
        p = Project(name=name, path=path, added=str(date.today()), **kwargs)
        self._repo.add(p)
        self._sync.quick_sync(["projects.yml"], "add")
        return p

    def remove(self, query: str) -> Project | None:
        entry = self._repo.resolve(query)
        if entry is None:
            return None
        removed = self._repo.remove(entry.slug)
        if removed:
            self._sync.quick_sync(["projects.yml"], "remove")
        return removed

    def edit(self, query: str, **kwargs) -> Project | None:
        entry = self._repo.resolve(query)
        if entry is None:
            return None
        updated = self._repo.update(entry.slug, **kwargs)
        if updated:
            self._sync.quick_sync(["projects.yml"], "edit")
        return updated

    def resolve(self, query: str) -> Project | None:
        return self._repo.resolve(query)

    def resolve_all(self, query: str) -> list[Project]:
        return self._repo.resolve_all(query)

    def resolve_by_path(self, path: str) -> Project | None:
        return self._repo.resolve_by_path(path)

    def list_all(self) -> list[Project]:
        return self._repo.load_all()

    def get(self, slug: str) -> Project | None:
        return self._repo.get(slug)
