from __future__ import annotations
from datetime import date
from nexus.config import NexusConfig
from nexus.models import CodexEntry
from nexus.repositories.codex_repo import CodexRepository
from nexus.services.sync_service import SyncService
from nexus.slug import slugify


class CodexService:
    def __init__(self, config: NexusConfig, sync: SyncService):
        self._repo = CodexRepository(config)
        self._sync = sync

    def add(self, title: str, kind: str = "referência", content: str = "", **kwargs) -> CodexEntry:
        slug = slugify(title)
        if self._repo.get(slug) is not None:
            raise ValueError(f"Codex entry with slug '{slug}' already exists")
        entry = CodexEntry(
            slug=slug, title=title, kind=kind, content=content,
            created=str(date.today()), **kwargs,
        )
        self._repo.save(entry)
        self._sync.quick_sync([f"codex/{slug}.md"], "codex-add")
        return entry

    def remove(self, query: str) -> CodexEntry | None:
        entry = self._repo.resolve(query)
        if entry is None:
            return None
        removed = self._repo.remove(entry.slug)
        if removed:
            self._sync.quick_sync(["codex/"], "codex-remove")
        return removed

    def edit(self, slug: str, **kwargs) -> CodexEntry | None:
        entry = self._repo.get(slug)
        if entry is None:
            return None
        for key, value in kwargs.items():
            setattr(entry, key, value)
        entry.updated = str(date.today())
        self._repo.save(entry)
        self._sync.quick_sync([f"codex/{slug}.md"], "codex-edit")
        return entry

    def resolve(self, query: str) -> CodexEntry | None:
        return self._repo.resolve(query)

    def list_all(self) -> list[CodexEntry]:
        return self._repo.load_all()
