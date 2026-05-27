from __future__ import annotations
from dataclasses import dataclass


@dataclass
class App:
    name: str
    slug: str = ""
    description: str = ""
    icon: str | None = None
    domain: str = "pessoal"
    github: str | None = None
    url: str | None = None
    note: str | None = None
    added: str = ""

    def to_dict(self) -> dict:
        d: dict = {"name": self.name, "slug": self.slug}
        if self.description:
            d["description"] = self.description
        if self.icon is not None:
            d["icon"] = self.icon
        d["domain"] = self.domain
        if self.github is not None:
            d["github"] = self.github
        if self.url is not None:
            d["url"] = self.url
        if self.note is not None:
            d["note"] = self.note
        if self.added:
            d["added"] = self.added
        return d

    @classmethod
    def from_dict(cls, data: dict) -> App:
        return cls(
            name=data["name"],
            slug=data.get("slug", ""),
            description=data.get("description", ""),
            icon=data.get("icon"),
            domain=data.get("domain", data.get("category", "pessoal")),
            github=data.get("github"),
            url=data.get("url"),
            note=data.get("note"),
            added=str(data.get("added", "")),
        )
