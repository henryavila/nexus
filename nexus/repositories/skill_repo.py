from __future__ import annotations
from nexus.config import NexusConfig
from nexus.models import Skill
from .base import MarkdownRepository


class SkillRepository(MarkdownRepository[Skill]):
    def __init__(self, config: NexusConfig):
        super().__init__(directory=config.skills_dir, model=Skill)
