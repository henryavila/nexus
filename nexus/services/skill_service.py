from __future__ import annotations
from datetime import date
from nexus.config import NexusConfig
from nexus.models import Skill
from nexus.repositories.skill_repo import SkillRepository
from nexus.services.sync_service import SyncService
from nexus.slug import slugify


class SkillService:
    def __init__(self, config: NexusConfig, sync: SyncService):
        self._repo = SkillRepository(config)
        self._sync = sync

    def add(self, title: str, scope: str = "global", **kwargs) -> Skill:
        slug = slugify(title)
        if self._repo.get(slug) is not None:
            raise ValueError(f"Skill with slug '{slug}' already exists")
        entry = Skill(
            title=title, slug=slug, scope=scope,
            added=str(date.today()), **kwargs,
        )
        self._repo.save(entry)
        self._sync.quick_sync([f"skills/{slug}.md"], "skill-add")
        return entry

    def remove(self, query: str) -> Skill | None:
        entry = self._repo.resolve(query)
        if entry is None:
            return None
        removed = self._repo.remove(entry.slug)
        if removed:
            self._sync.quick_sync(["skills/"], "skill-remove")
        return removed

    def edit(self, query: str, **kwargs) -> Skill | None:
        entry = self._repo.resolve(query)
        if entry is None:
            return None
        for key, value in kwargs.items():
            setattr(entry, key, value)
        self._repo.save(entry)
        self._sync.quick_sync([f"skills/{entry.slug}.md"], "skill-edit")
        return entry

    def resolve(self, query: str) -> Skill | None:
        return self._repo.resolve(query)

    def resolve_all(self, query: str) -> list[Skill]:
        return self._repo.resolve_all(query)

    def list_all(self) -> list[Skill]:
        return self._repo.load_all()
