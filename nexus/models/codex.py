from __future__ import annotations
from dataclasses import dataclass


@dataclass
class CodexEntry:
    slug: str = ""
    title: str = ""
    kind: str = "referência"
    domain: str = "pessoal"
    order: int | None = None
    created: str = ""
    updated: str = ""
    content: str = ""

    def to_frontmatter(self) -> dict:
        meta: dict = {"title": self.title}
        if self.kind:
            meta["kind"] = self.kind
        if self.domain:
            meta["domain"] = self.domain
        if self.order is not None:
            meta["order"] = self.order
        if self.created:
            meta["created"] = self.created
        if self.updated:
            meta["updated"] = self.updated
        return meta

    @classmethod
    def from_frontmatter(cls, slug: str, meta: dict, content: str) -> CodexEntry:
        return cls(
            slug=slug,
            title=meta.get("title", slug),
            kind=meta.get("kind", meta.get("category", "referência")),
            domain=meta.get("domain", "pessoal"),
            order=meta.get("order"),
            created=str(meta["created"]) if "created" in meta else "",
            updated=str(meta["updated"]) if "updated" in meta else "",
            content=content,
        )
