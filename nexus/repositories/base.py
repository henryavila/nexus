from __future__ import annotations

from pathlib import Path
from typing import TypeVar, Generic

import yaml

T = TypeVar("T")


class YamlRepository(Generic[T]):
    def __init__(self, path: Path, model: type[T], collection_key: str, id_field: str = "slug",
                 lock_path: Path | None = None):
        self._path = path
        self._model = model
        self._collection_key = collection_key
        self._id_field = id_field
        self._lock_path = lock_path or path.parent / ".nexus.lock"

    @property
    def path(self) -> Path:
        return self._path

    def _ensure_file(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if not self._path.exists():
            self._path.write_text(f"{self._collection_key}: []\n", encoding="utf-8")

    def _load_raw(self) -> list[dict]:
        self._ensure_file()
        data = yaml.safe_load(self._path.read_text(encoding="utf-8")) or {}
        return data.get(self._collection_key) or []

    def _save_raw(self, items: list[T]) -> None:
        self._ensure_file()
        data = {self._collection_key: [item.to_dict() for item in items]}
        with open(self._path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    def load_all(self) -> list[T]:
        from nexus.infra.file_lock import file_lock
        with file_lock(self._lock_path):
            raw = self._load_raw()
        return [self._model.from_dict(item) for item in raw if isinstance(item, dict)]

    def save_all(self, items: list[T]) -> None:
        from nexus.infra.file_lock import file_lock
        with file_lock(self._lock_path):
            self._save_raw(items)

    def get(self, id_value: str) -> T | None:
        for item in self.load_all():
            if getattr(item, self._id_field) == id_value:
                return item
        return None

    def add(self, item: T) -> None:
        from nexus.infra.file_lock import file_lock
        with file_lock(self._lock_path):
            raw = self._load_raw()
            items = [self._model.from_dict(r) for r in raw if isinstance(r, dict)]
            items.append(item)
            self._save_raw(items)

    def update(self, id_value: str, **kwargs) -> T | None:
        from nexus.infra.file_lock import file_lock
        with file_lock(self._lock_path):
            raw = self._load_raw()
            items = [self._model.from_dict(r) for r in raw if isinstance(r, dict)]
            for i, item in enumerate(items):
                if getattr(item, self._id_field) == id_value:
                    for key, value in kwargs.items():
                        setattr(items[i], key, value)
                    self._save_raw(items)
                    return items[i]
        return None

    def remove(self, id_value: str) -> T | None:
        from nexus.infra.file_lock import file_lock
        with file_lock(self._lock_path):
            raw = self._load_raw()
            items = [self._model.from_dict(r) for r in raw if isinstance(r, dict)]
            for i, item in enumerate(items):
                if getattr(item, self._id_field) == id_value:
                    removed = items.pop(i)
                    self._save_raw(items)
                    return removed
        return None

    def resolve(self, query: str) -> T | None:
        results = self.resolve_all(query)
        return results[0] if results else None

    def resolve_all(self, query: str) -> list[T]:
        items = self.load_all()
        q = query.lower().strip()
        slug_hit = None
        for item in items:
            if getattr(item, self._id_field, "").lower() == q:
                slug_hit = item
                break
        by_name = [
            item for item in items
            if (getattr(item, "name", None) or getattr(item, "title", None) or "").lower() == q
        ]
        if slug_hit and not by_name:
            return [slug_hit]
        if by_name:
            if slug_hit and slug_hit not in by_name:
                return [slug_hit] + by_name
            return by_name
        by_partial_id = [
            item for item in items
            if q in getattr(item, self._id_field, "").lower()
        ]
        if by_partial_id:
            return by_partial_id
        by_partial_name = [
            item for item in items
            if q in (getattr(item, "name", None) or getattr(item, "title", None) or "").lower()
        ]
        return by_partial_name


class MarkdownRepository(Generic[T]):
    def __init__(self, directory: Path, model: type[T]):
        self._directory = directory
        self._model = model

    @property
    def directory(self) -> Path:
        return self._directory

    def _ensure_dir(self) -> None:
        self._directory.mkdir(parents=True, exist_ok=True)

    def _safe_path(self, slug: str) -> Path:
        md_file = (self._directory / f"{slug}.md").resolve()
        if not md_file.is_relative_to(self._directory.resolve()):
            raise ValueError(f"Invalid slug: {slug!r}")
        return md_file

    def _parse_frontmatter(self, text: str) -> tuple[dict, str]:
        if not text.startswith("---"):
            return {}, text
        parts = text.split("---", 2)
        if len(parts) < 3:
            return {}, text
        meta = yaml.safe_load(parts[1]) or {}
        content = parts[2].strip()
        return meta, content

    def _render_frontmatter(self, meta: dict, content: str) -> str:
        fm = yaml.dump(meta, default_flow_style=False, allow_unicode=True, sort_keys=False).strip()
        if content:
            return f"---\n{fm}\n---\n\n{content}\n"
        return f"---\n{fm}\n---\n"

    def load_all(self) -> list[T]:
        self._ensure_dir()
        entries = []
        for md_file in sorted(self._directory.glob("*.md")):
            text = md_file.read_text(encoding="utf-8")
            meta, content = self._parse_frontmatter(text)
            entries.append(self._model.from_frontmatter(md_file.stem, meta, content))
        return entries

    def get(self, slug: str) -> T | None:
        md_file = self._safe_path(slug)
        if not md_file.exists():
            return None
        text = md_file.read_text(encoding="utf-8")
        meta, content = self._parse_frontmatter(text)
        return self._model.from_frontmatter(slug, meta, content)

    def save(self, entry: T) -> None:
        self._ensure_dir()
        slug = getattr(entry, "slug")
        md_file = self._safe_path(slug)
        meta = entry.to_frontmatter()
        content = getattr(entry, "content", "")
        md_file.write_text(self._render_frontmatter(meta, content), encoding="utf-8")

    def remove(self, slug: str) -> T | None:
        entry = self.get(slug)
        if entry is None:
            return None
        md_file = self._safe_path(slug)
        md_file.unlink()
        return entry

    def resolve(self, query: str) -> T | None:
        entries = self.load_all()
        q = query.lower().strip()
        for e in entries:
            if getattr(e, "slug", "").lower() == q:
                return e
        for e in entries:
            title = getattr(e, "title", "")
            if title.lower() == q:
                return e
        for e in entries:
            if q in getattr(e, "slug", "").lower():
                return e
        return None
