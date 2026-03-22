"""Knowledge cache: search and window builders."""

import unittest

from qhpc_cache.knowledge_cache import (
    build_concept_note_library,
    build_critical_cache_window,
    build_default_research_reference_set,
    search_critical_cache_window,
)


class TestKnowledgeCacheExtended(unittest.TestCase):
    def test_search_finds_var(self):
        hits = search_critical_cache_window("var")
        self.assertTrue(any("var" in h.concept_id for h in hits))

    def test_build_window(self):
        window = build_critical_cache_window()
        self.assertGreater(len(window.concepts), 0)

    def test_reference_set(self):
        refs = build_default_research_reference_set()
        self.assertGreaterEqual(len(refs), 1)

    def test_concept_notes(self):
        notes = build_concept_note_library()
        self.assertGreaterEqual(len(notes), 1)


if __name__ == "__main__":
    unittest.main()
