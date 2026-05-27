from __future__ import annotations
from dataclasses import dataclass


@dataclass
class Project:
    name: str
    path: str | None = None
    slug: str = ""
    description: str = ""
    icon: str | None = None
    domain: str = "pessoal"
    nature: str = "contexto"
    private: bool = False
    url: str | None = None
    repo: str | None = None
    status: str | None = None
    note: str | None = None
    added: str = ""
    web: dict | None = None

    def to_dict(self) -> dict:
        d: dict = {"name": self.name}
        if self.path is not None:
            d["path"] = self.path
        if self.slug:
            d["slug"] = self.slug
        if self.description:
            d["description"] = self.description
        if self.icon is not None:
            d["icon"] = self.icon
        d["domain"] = self.domain
        d["nature"] = self.nature
        if self.private:
            d["private"] = True
        if self.url is not None:
            d["url"] = self.url
        if self.repo is not None:
            d["repo"] = self.repo
        if self.status is not None:
            d["status"] = self.status
        if self.note is not None:
            d["note"] = self.note
        if self.added:
            d["added"] = self.added
        if self.web is not None:
            d["web"] = self.web
        return d

    @classmethod
    def from_dict(cls, data: dict) -> Project:
        return cls(
            name=data["name"],
            path=data.get("path"),
            slug=data.get("slug", ""),
            description=data.get("description", ""),
            icon=data.get("icon"),
            domain=data.get("domain", data.get("category", "pessoal")),
            nature=data.get("nature", "contexto"),
            private=data.get("private", False),
            url=data.get("url"),
            repo=data.get("repo"),
            status=data.get("status"),
            note=data.get("note"),
            added=str(data.get("added", "")),
            web=data.get("web"),
        )
