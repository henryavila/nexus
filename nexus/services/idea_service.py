from __future__ import annotations
from datetime import date
from nexus.config import NexusConfig
from nexus.models import Idea
from nexus.repositories.idea_repo import IdeaRepository
from nexus.services.sync_service import SyncService


class IdeaService:
    def __init__(self, config: NexusConfig, sync: SyncService):
        self._repo = IdeaRepository(config)
        self._sync = sync

    def add(self, title: str, **kwargs) -> Idea:
        i = Idea(title=title, created=str(date.today()), **kwargs)
        self._repo.add(i)
        self._sync.quick_sync(["ideas.yml"], "idea-add")
        return i

    def remove(self, query: str) -> Idea | None:
        entry = self._repo.resolve(query)
        if entry is None:
            return None
        removed = self._repo.remove(entry.id)
        if removed:
            self._sync.quick_sync(["ideas.yml"], "idea-remove")
        return removed

    def edit(self, query: str, **kwargs) -> Idea | None:
        entry = self._repo.resolve(query)
        if entry is None:
            return None
        updated = self._repo.update(entry.id, **kwargs)
        if updated:
            self._sync.quick_sync(["ideas.yml"], "idea-edit")
        return updated

    def resolve(self, query: str) -> Idea | None:
        return self._repo.resolve(query)

    def resolve_all(self, query: str) -> list[Idea]:
        return self._repo.resolve_all(query)

    def list_all(self) -> list[Idea]:
        return self._repo.load_all()
