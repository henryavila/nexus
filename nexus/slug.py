from __future__ import annotations

import re
import unicodedata


def slugify(text: str) -> str:
    """Convert text to a full URL-safe slug: lowercase, hyphens, no accents."""
    if not text:
        return ""
    # Decompose unicode and strip accents (combining marks)
    nfkd = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(c for c in nfkd if not unicodedata.combining(c))
    # Remove non-alphanumeric except hyphens and spaces
    cleaned = re.sub(r"[^\w\s-]", "", ascii_text)
    # Replace whitespace/underscores with hyphens, collapse multiples
    slug = re.sub(r"[\s_]+", "-", cleaned.strip())
    # Collapse multiple hyphens
    slug = re.sub(r"-+", "-", slug)
    # Strip leading/trailing hyphens and lowercase
    return slug.strip("-").lower()


def make_short_slug(name: str) -> str:
    """Generate a short slug from a project name.

    Logic B:
    - Single word (already short) → the word itself, lowercased
    - 2+ words → first letter of each word, lowercased
    """
    if not name:
        return ""
    # First sanitize: strip accents and non-alpha chars, split into words
    nfkd = unicodedata.normalize("NFKD", name)
    ascii_text = "".join(c for c in nfkd if not unicodedata.combining(c))
    # Remove non-alphanumeric except hyphens and spaces
    cleaned = re.sub(r"[^\w\s-]", "", ascii_text).strip()
    # Split on spaces and hyphens to get words
    words = re.split(r"[\s-]+", cleaned)
    words = [w for w in words if w]  # remove empties
    if not words:
        return ""
    if len(words) == 1:
        return words[0].lower()
    # Multi-word: take first letter of each word
    return "".join(w[0] for w in words).lower()
