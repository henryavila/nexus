from __future__ import annotations
from datetime import date
from nexus.config import NexusConfig
from nexus.models import App
from nexus.repositories.app_repo import AppRepository
from nexus.services.sync_service import SyncService


class AppService:
    def __init__(self, config: NexusConfig, sync: SyncService):
        self._repo = AppRepository(config)
        self._sync = sync

    def add(self, name: str, **kwargs) -> App:
        a = App(name=name, added=str(date.today()), **kwargs)
        self._repo.add(a)
        self._sync.quick_sync(["apps.yml"], "app-add")
        return a

    def remove(self, query: str) -> App | None:
        entry = self._repo.resolve(query)
        if entry is None:
            return None
        removed = self._repo.remove(entry.slug)
        if removed:
            self._sync.quick_sync(["apps.yml"], "app-remove")
        return removed

    def edit(self, query: str, **kwargs) -> App | None:
        entry = self._repo.resolve(query)
        if entry is None:
            return None
        updated = self._repo.update(entry.slug, **kwargs)
        if updated:
            self._sync.quick_sync(["apps.yml"], "app-edit")
        return updated

    def resolve(self, query: str) -> App | None:
        return self._repo.resolve(query)

    def resolve_all(self, query: str) -> list[App]:
        return self._repo.resolve_all(query)

    def list_all(self) -> list[App]:
        return self._repo.load_all()
