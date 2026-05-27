from __future__ import annotations
from dataclasses import dataclass


@dataclass
class Skill:
    title: str = ""
    slug: str = ""
    scope: str = "global"
    url: str | None = None
    added: str = ""
    content: str = ""

    def to_frontmatter(self) -> dict:
        meta: dict = {"title": self.title}
        if self.slug:
            meta["slug"] = self.slug
        meta["scope"] = self.scope
        if self.url:
            meta["url"] = self.url
        if self.added:
            meta["added"] = self.added
        return meta

    @classmethod
    def from_frontmatter(cls, slug: str, meta: dict, content: str) -> Skill:
        return cls(
            title=str(meta.get("title", slug)),
            slug=str(meta.get("slug", slug)),
            scope=str(meta.get("scope", "global")),
            url=meta.get("url"),
            added=str(meta.get("added", "")),
            content=content,
        )
