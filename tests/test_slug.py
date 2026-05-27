import unittest

from nexus.slug import slugify, make_short_slug


class SlugifyTests(unittest.TestCase):
    """slugify() sanitizes text into a URL-safe slug (full, not abbreviated)."""

    def test_simple_lowercase(self):
        self.assertEqual(slugify("nexus"), "nexus")

    def test_spaces_to_hyphens(self):
        self.assertEqual(slugify("Dragon Heir"), "dragon-heir")

    def test_accents_stripped(self):
        self.assertEqual(slugify("Gestão Atividades"), "gestao-atividades")

    def test_special_chars_removed(self):
        self.assertEqual(slugify("IA Builder (v2)"), "ia-builder-v2")

    def test_multiple_spaces_collapsed(self):
        self.assertEqual(slugify("Lucio  Monteiro  Kids"), "lucio-monteiro-kids")

    def test_leading_trailing_hyphens_stripped(self):
        self.assertEqual(slugify(" - hello - "), "hello")

    def test_existing_slugs_preserved(self):
        self.assertEqual(slugify("dh"), "dh")

    def test_empty_string(self):
        self.assertEqual(slugify(""), "")

    def test_unicode_emoji_removed(self):
        self.assertEqual(slugify("🐉 Dragon"), "dragon")

    def test_hyphens_preserved(self):
        self.assertEqual(slugify("wsl-config"), "wsl-config")

    def test_incidentes_getin(self):
        self.assertEqual(slugify("Incidentes-Getin"), "incidentes-getin")


class MakeShortSlugTests(unittest.TestCase):
    """make_short_slug() generates abbreviated slugs (logic B):
    - Single short word → itself
    - 2+ words → initials
    """

    # Single words → kept as-is
    def test_single_word_short(self):
        self.assertEqual(make_short_slug("nexus"), "nexus")

    def test_single_word_acronym(self):
        self.assertEqual(make_short_slug("CRCMG"), "crcmg")

    def test_single_word_mnemo(self):
        self.assertEqual(make_short_slug("Mnemo"), "mnemo")

    def test_single_word_livros(self):
        self.assertEqual(make_short_slug("Livros"), "livros")

    # Multi-word → initials (first letter of each word)
    def test_two_words_initials(self):
        self.assertEqual(make_short_slug("Dragon Heir"), "dh")

    def test_two_words_ia_builder(self):
        # "IA" and "Builder" → first letter of each → "ib"
        self.assertEqual(make_short_slug("IA Builder"), "ib")

    def test_two_words_wsl_config(self):
        self.assertEqual(make_short_slug("WSL Config"), "wc")

    def test_three_words_initials(self):
        self.assertEqual(make_short_slug("Lucio Monteiro Kids"), "lmk")

    def test_hyphenated_words_as_multi(self):
        self.assertEqual(make_short_slug("Incidentes-Getin"), "ig")

    # Edge cases
    def test_empty_string(self):
        self.assertEqual(make_short_slug(""), "")

    def test_accented_initials(self):
        self.assertEqual(make_short_slug("Gestão Atividades"), "ga")

    def test_emoji_ignored_in_initials(self):
        self.assertEqual(make_short_slug("🐉 Dragon Heir"), "dh")


if __name__ == "__main__":
    unittest.main()
