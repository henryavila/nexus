from __future__ import annotations
from dataclasses import dataclass


@dataclass
class Idea:
    title: str = ""
    id: str = ""
    description: str = ""
    domain: str = "pessoal"
    priority: str = "medium"
    references: list[str] | None = None
    notes: str | None = None
    created: str = ""

    def to_dict(self) -> dict:
        d: dict = {}
        if self.id:
            d["id"] = self.id
        d["title"] = self.title
        if self.description:
            d["description"] = self.description
        d["domain"] = self.domain
        d["priority"] = self.priority
        if self.references is not None:
            d["references"] = self.references
        if self.notes is not None:
            d["notes"] = self.notes
        if self.created:
            d["created"] = self.created
        return d

    @classmethod
    def from_dict(cls, data: dict) -> Idea:
        return cls(
            id=data.get("id", ""),
            title=data.get("title", ""),
            description=data.get("description", ""),
            domain=data.get("domain", data.get("category", "pessoal")),
            priority=data.get("priority", "medium"),
            references=data.get("references"),
            notes=data.get("notes"),
            created=str(data.get("created", "")),
        )
