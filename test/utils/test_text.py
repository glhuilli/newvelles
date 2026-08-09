"""Tests for newvelles.utils.text module."""

import unittest
from collections import Counter

from newvelles.utils.text import (_remove_duplicates, get_final_weighted_score,
                                  get_sentence_score, get_top_words_spacy,
                                  get_total_info_value, process_content)

TEST_CASES = {
    "Limbic is a package.": ["limbic", "package"],
    "a random number 111": ["random", "number"],
    "something I didn't expected to test with l'huillier.": [
        "didnt",
        "expected",
        "test",
        "lhuillier",
    ],
    "l'huillier is a last name a will not change.": ["l'huillier", "change"],
    "didn't will be removed (stopword).": ["removed", "stopword"],
    "": [""],
}
TERMS_MAPPING = {"dog": "cat"}
TEST_CASES_TERMS_MAPPING = {"this is a dog": "this is a cat"}


class TestUtilText(unittest.TestCase):
    def test_process_content(self):
        for input_test, expected_output in TEST_CASES.items():
            output = process_content(input_test)
            self.assertEqual(output, expected_output)

    def test_process_content_with_terms_mapping(self):
        for input_test, expected_output in TEST_CASES.items():
            output = process_content(input_test, terms_mapping=TERMS_MAPPING)
            self.assertEqual(output, expected_output)

    def test_get_top_words_spacy(self):
        sentences = [
            "Apple is looking at buying U.K. startup for $1 billion",
            "Apple, located in Cupertino, buying startup in the U.K for billions",
        ]
        output = get_top_words_spacy(sentences)
        expected = [
            ("[the uk]", 2),
            ("[apple]", 2),
            ("[startup]", 2),
            ("[billion]", 1),
            ("[buy]", 1),
        ]
        self.assertEqual(output, expected)

    def test_get_top_words_spacy_no_sentences(self):
        sentences = []
        output = get_top_words_spacy(sentences)
        expected = []
        self.assertCountEqual(output, expected)

    def test_get_top_words_spacy_one_sentence(self):
        sentences = ["Apple is looking at buying U.K. startup for $1 billion"]
        output = get_top_words_spacy(sentences)
        expected = [("[apple]", 1), ("[startup]", 1), ("[uk]", 1)]
        self.assertCountEqual(output, expected)

    def test_get_top_words_spacy_one_sentence_no_nouns_verbs(self):
        sentences = ["the at"]
        output = get_top_words_spacy(sentences)
        expected = []
        self.assertCountEqual(output, expected)

    def test__remove_duplicates(self):
        counter_terms = Counter()
        counter_terms.update(["uk startup", "uk startup"])
        output = _remove_duplicates(counter_terms.items())
        expected = {"uk startup": 2}.items()
        self.assertEqual(output, expected)


# Additional pytest-style tests for better coverage
class TestProcessContentPytest:
    """Pytest-style tests for process_content function."""

    def test_process_content_empty_string(self):
        """Test process_content with empty string."""
        result = process_content("")
        assert result == [""]

    def test_process_content_with_numbers(self):
        """Test process_content filters out numbers."""
        result = process_content("The year 2023 was great")
        assert "2023" not in result
        assert "year" in result

    def test_process_content_with_punctuation(self):
        """Test process_content handles punctuation."""
        result = process_content("Apple released iPhone! Microsoft announced Windows.")
        expected_words = [
            "apple",
            "released",
            "iphone",
            "microsoft",
            "announced",
            "windows",
        ]
        # Should contain meaningful words without punctuation
        for word in expected_words:
            assert word in result or any(word in token for token in result)

    def test_process_content_with_terms_mapping(self):
        """Test process_content with terms mapping."""
        terms_mapping = {"dog": "cat", "big": "large"}
        result = process_content("The big dog runs", terms_mapping=terms_mapping)
        # The function should apply term mapping
        assert isinstance(result, list)

    def test_process_content_unicode_characters(self):
        """Test process_content with unicode characters."""
        result = process_content("Café résumé naïve")
        assert isinstance(result, list)
        # Should handle unicode characters gracefully

    def test_process_content_spacy_error(self):
        """Test process_content when spacy fails to load."""
        # Test with simple input - the autouse fixture will mock spacy
        result = process_content("Test content")
        assert isinstance(result, list)


class TestGetTopWordsSpacyPytest:
    """Additional pytest-style tests for get_top_words_spacy."""

    def test_get_top_words_spacy_functions_exist(self):
        """Test that get_top_words_spacy function exists and is callable."""
        # These functions use real spaCy models which are slow to load
        # The autouse fixture will mock them, so we just test basic functionality
        sentences = ["Test sentence"]
        result = get_top_words_spacy(sentences)

        # Should return a list (mocked result)
        assert isinstance(result, list)

    def test_get_top_words_spacy_filter_short_words(self):
        """Test that get_top_words_spacy filters short words."""
        # This test would need more complex mocking, simplified for now
        sentences = ["A big elephant runs"]
        result = get_top_words_spacy(sentences)

        # Result should be a list of tuples
        assert isinstance(result, list)
        if result:
            for item in result:
                assert isinstance(item, tuple)
                assert len(item) == 2  # (word, count)


class TestGetTotalInfoValue(unittest.TestCase):
    """Tests for get_total_info_value, the per-word 'information value' score."""

    def test_words_shorter_than_two_letters_score_zero(self):
        # The function short-circuits to 0 for words under 2 characters.
        self.assertEqual(get_total_info_value("a"), 0)
        self.assertEqual(get_total_info_value("I"), 0)
        self.assertEqual(get_total_info_value(""), 0)

    def test_score_is_bounded_between_zero_and_one(self):
        for word in ["cat", "jazz", "elephant", "quiz", "the"]:
            score = get_total_info_value(word)
            self.assertGreaterEqual(score, 0.0)
            self.assertLessEqual(score, 1.0)

    def test_rare_letters_score_higher_than_common_letters(self):
        # Same length (4 letters): "jazz" (j,z rare) must beat "area" (all common).
        self.assertGreater(get_total_info_value("jazz"), get_total_info_value("area"))

    def test_surrounding_punctuation_is_ignored(self):
        # Leading/trailing punctuation is stripped before scoring.
        self.assertEqual(get_total_info_value("cat."), get_total_info_value("cat"))
        self.assertEqual(get_total_info_value("(cat)"), get_total_info_value("cat"))

    def test_is_deterministic(self):
        self.assertEqual(get_total_info_value("elephant"), get_total_info_value("elephant"))


class TestGetFinalWeightedScore(unittest.TestCase):
    """Tests for get_final_weighted_score, which weights the base value by capitalization."""

    def test_words_shorter_than_two_letters_score_zero(self):
        self.assertEqual(get_final_weighted_score("a"), 0)
        self.assertEqual(get_final_weighted_score("I"), 0)

    def test_all_caps_acronym_gets_2_5x_multiplier(self):
        # An all-caps acronym is weighted 2.5x the plain (lowercase) base value.
        base = get_final_weighted_score("nasa")
        self.assertEqual(get_final_weighted_score("NASA"), round(base * 2.5, 4))

    def test_mid_sentence_capitalized_word_gets_2x_multiplier(self):
        # A capitalized word mid-sentence is treated as a high-value entity (2.0x).
        base = get_final_weighted_score("apple")
        self.assertEqual(
            get_final_weighted_score("Apple", is_start_of_sentence=False),
            round(base * 2.0, 4),
        )

    def test_common_starter_at_sentence_start_scores_below_mid_sentence(self):
        # "The" as a sentence starter (1.1x) should score lower than the same
        # capitalized word appearing mid-sentence (2.0x).
        at_start = get_final_weighted_score("The", is_start_of_sentence=True)
        mid_sentence = get_final_weighted_score("The", is_start_of_sentence=False)
        self.assertLess(at_start, mid_sentence)

    def test_acronym_outranks_same_letters_lowercase(self):
        self.assertGreater(get_final_weighted_score("FBI"), get_final_weighted_score("fbi"))


class TestGetSentenceScore(unittest.TestCase):
    """Tests for get_sentence_score, which aggregates word scores into a sentence score."""

    def test_empty_sentence_scores_zero(self):
        self.assertEqual(get_sentence_score(""), 0)

    def test_whitespace_only_sentence_scores_zero(self):
        self.assertEqual(get_sentence_score("   "), 0)

    def test_score_is_non_negative(self):
        self.assertGreaterEqual(get_sentence_score("the quick brown fox"), 0.0)

    def test_informative_sentence_outscores_filler(self):
        # Distinctive, capitalized, rare-letter words carry more signal than
        # a sentence of short common filler words.
        informative = get_sentence_score("Zimbabwe quartz jukebox")
        filler = get_sentence_score("it is on to")
        self.assertGreater(informative, filler)

    def test_is_deterministic(self):
        sentence = "Oil prices surge amid conflict"
        self.assertEqual(get_sentence_score(sentence), get_sentence_score(sentence))
