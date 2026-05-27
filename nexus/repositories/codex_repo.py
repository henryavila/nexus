from __future__ import annotations
from nexus.config import NexusConfig
from nexus.models import CodexEntry
from .base import MarkdownRepository


class CodexRepository(MarkdownRepository[CodexEntry]):
    def __init__(self, config: NexusConfig):
        super().__init__(directory=config.codex_dir, model=CodexEntry)
