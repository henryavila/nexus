from __future__ import annotations

from typing import Any

try:
    from textual.suggester import Suggester
except ModuleNotFoundError:
    class Suggester:
        def __init__(self, *args, **kwargs):
            pass

from nexus.constants import DEFAULT_DOMAINS, PROJECT_NATURES, CODEX_KINDS

_NATURE_ALIASES = {
    "ctx": "contexto", "tool": "ferramenta", "app": "companion",
    "contexto": "contexto", "ferramenta": "ferramenta", "companion": "companion",
}


def _parse_filter(text: str) -> dict:
    """Parse filter input with d:, n:, k: prefixes. Returns {text, d, n, k}."""
    parts = text.strip().split()
    result = {"text": "", "d": None, "n": None, "k": None}
    text_parts = []
    for part in parts:
        if part.startswith("d:") and len(part) > 2:
            result["d"] = part[2:]
        elif part.startswith("n:") and len(part) > 2:
            result["n"] = _NATURE_ALIASES.get(part[2:], part[2:])
        elif part.startswith("k:") and len(part) > 2:
            result["k"] = part[2:]
        else:
            text_parts.append(part)
    result["text"] = " ".join(text_parts)
    return result


class FilterSuggester(Suggester):
    """Autocomplete for d:, n:, k: filter prefixes."""

    async def get_suggestion(self, value: str) -> str | None:
        if not value:
            return None
        parts = value.split()
        last = parts[-1] if parts else ""
        prefix_map = {"d:": DEFAULT_DOMAINS, "n:": PROJECT_NATURES, "k:": CODEX_KINDS}
        for pfx, options in prefix_map.items():
            if last.startswith(pfx) and len(last) > len(pfx):
                typed = last[len(pfx):]
                for opt in options:
                    if opt.startswith(typed) and opt != typed:
                        completed = pfx + opt
                        return " ".join(parts[:-1] + [completed]).strip()
        return None
