from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class Environment:
    hostname: str
    name: str
    location: str = ""
    last_seen: str = ""
    paths: dict[str, str] = field(default_factory=dict)
    absent: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d: dict = {"hostname": self.hostname, "name": self.name}
        if self.location:
            d["location"] = self.location
        if self.last_seen:
            d["last_seen"] = self.last_seen
        if self.paths:
            d["paths"] = self.paths
        if self.absent:
            d["absent"] = self.absent
        return d

    @classmethod
    def from_dict(cls, data: dict) -> Environment:
        return cls(
            hostname=data["hostname"],
            name=data.get("name", data["hostname"]),
            location=data.get("location", ""),
            last_seen=str(data.get("last_seen", "")),
            paths=data.get("paths") or {},
            absent=data.get("absent") or [],
        )
