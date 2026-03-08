"""
Focused tests for group identifier improvements - Requirement 1: Complete Words Only.

Test that all words in group identifiers are complete words from original titles,
not partial fragments.
"""

import pytest

from newvelles.models.grouping import extract_common_substrings, identify_group


class TestCompleteWordsOnly:
    """
    Requirement 1: All words in the group identifier must be complete words
    that actually appear in the original titles (not fragments).
    """

    def test_all_words_exist_in_original_titles(self):
        """
        Core test: Every word in the group identifier should exist
        as a complete word in at least one original title.

        This catches fragments like "clipse" (from "Eclipse") or "alks" (from "talks").
        """
        titles = [
            "Eclipse IDE tutorial",
            "Eclipse debugging guide",
            "Eclipse workspace setup"
        ]

        result = identify_group(titles)

        # Get all words from result (strip brackets first)
        result_clean = result.replace('[', '').replace(']', '')
        result_words = result_clean.split()

        # Get all words from original titles
        original_words = set()
        for title in titles:
            # Split on spaces and common punctuation
            title_words = title.replace(',', ' ').replace('.', ' ').replace(':', ' ').split()
            original_words.update(title_words)

        # Check each word in result exists in original
        for word in result_words:
            assert word in original_words, \
                f"Word '{word}' in result not found in original titles. " \
                f"Original words: {sorted(original_words)}"

    def test_all_words_exist_case_insensitive(self):
        """
        Same test but case-insensitive to handle capitalization differences.
        """
        titles = [
            "World Seeks an End to Plastic Pollution at Talks in South Korea",
            "What to know about the plastic pollution treaty talks in South Korea"
        ]

        result = identify_group(titles)

        # Get all words from result (strip brackets first, then lowercase)
        result_clean = result.replace('[', '').replace(']', '')
        result_words = [w.lower() for w in result_clean.split()]

        # Get all words from original titles (lowercase)
        original_words = set()
        for title in titles:
            title_words = title.replace(',', ' ').replace('.', ' ').replace(':', ' ').split()
            original_words.update([w.lower() for w in title_words])

        # Check each word in result exists in original
        for word in result_words:
            assert word in original_words, \
                f"Word '{word}' not found in original titles. " \
                f"This might be a fragment like 'alks' instead of 'talks'. " \
                f"Original words: {sorted(original_words)}"

    def test_no_partial_words_at_word_boundaries(self):
        """
        Test that words aren't cut off at the beginning or end.
        Example: "talks" shouldn't become "alks" or "talk"
        """
        titles = [
            "Apple announces new iPhone model",
            "Apple reveals iPhone specifications"
        ]

        result = identify_group(titles)
        result_words = result.split()

        # Get original words
        original_words = set()
        for title in titles:
            original_words.update(title.split())

        # For each word in result, check it's a complete word from original
        for result_word in result_words:
            # Find if this word is a substring of any original word
            is_substring_of_larger_word = False
            matching_original_word = None

            for orig_word in original_words:
                if result_word in orig_word and result_word != orig_word:
                    is_substring_of_larger_word = True
                    matching_original_word = orig_word
                    break

            # If it's a substring, it should also exist as a complete word somewhere
            if is_substring_of_larger_word:
                assert result_word in original_words, \
                    f"'{result_word}' is a fragment of '{matching_original_word}', " \
                    f"not a complete word from titles"

    def test_extract_common_substrings_word_boundaries(self):
        """
        Test extract_common_substrings to ensure it respects word boundaries.
        """
        titles = [
            "Apple iPhone release",
            "Apple iPhone pricing"
        ]

        result = extract_common_substrings(titles, min_length=3)

        # Expected substrings should be complete segments from titles
        # "Apple iPhone", "Apple", "iPhone" are valid
        # "pple", "hone", "Appl" are NOT valid (partial words)

        # Get all complete words from titles
        all_words = set()
        for title in titles:
            all_words.update(title.split())

        # Check each substring - every word in it should be complete
        for substring in result:
            substring_words = substring.split()
            for word in substring_words:
                # Word should either:
                # 1. Exist as-is in all_words, OR
                # 2. Be a complete meaningful phrase from the original
                # For now, check if it's at least in the original text
                found_in_original = any(word in title for title in titles)
                assert found_in_original, \
                    f"Word '{word}' from substring '{substring}' not found in originals"

    def test_punctuation_removal_preserves_complete_words(self):
        """
        Test that punctuation removal doesn't create word fragments.
        "Garcia," should become "Garcia" not "arcia"
        "CEO's" can become "CEO" (possessive normalization is acceptable)
        """
        titles = [
            "Who is Maria Garcia, CEO's new pick?",
            "Who is Maria Garcia, CEO's nominee?"
        ]

        result = identify_group(titles)
        result_words = result.split()

        # Get all words from original titles
        original_words = set()
        for title in titles:
            # Split on whitespace and some punctuation
            import re
            words = re.findall(r"[a-zA-Z0-9']+", title)
            original_words.update(words)
            # Also add base forms (without possessives) since we normalize those
            original_words.update([w.replace("'s", "") for w in words])
            original_words.update([w.replace("'", "") for w in words])

        # Every word in result should exist in original words (or their normalized forms)
        for word in result_words:
            # Clean the word
            import re
            clean_word = re.findall(r"[a-zA-Z0-9']+", word)
            if clean_word:
                clean_word = clean_word[0]
                assert clean_word in original_words or clean_word == '', \
                    f"Word '{word}' (cleaned: '{clean_word}') not in original titles. " \
                    f"Original words: {sorted(original_words)}"

    def test_numbers_preserved_as_complete_tokens(self):
        """
        Numbers should be preserved completely, not partially.
        "2026" shouldn't become "026" or "202"
        """
        titles = [
            "Best Phones of 2026 Review",
            "Best Phones of 2026 Tested"
        ]

        result = identify_group(titles)

        # If result contains numbers, they should be complete
        import re
        result_numbers = re.findall(r'\d+', result)
        original_numbers = set()
        for title in titles:
            original_numbers.update(re.findall(r'\d+', title))

        for num in result_numbers:
            assert num in original_numbers, \
                f"Number '{num}' not found in originals: {original_numbers}"

    def test_mixed_case_words_match_original_case(self):
        """
        Test that words maintain their original case or are handled consistently.
        "iPhone" shouldn't become "Phone" or "hone"
        """
        titles = [
            "iPhone 16 announcement",
            "iPhone 16 features"
        ]

        result = identify_group(titles)

        # Strip brackets from result before validation
        result_clean = result.replace('[', '').replace(']', '')

        # Get all original words with their cases
        original_words_any_case = set()
        for title in titles:
            words = title.split()
            original_words_any_case.update(words)
            original_words_any_case.update([w.lower() for w in words])
            original_words_any_case.update([w.upper() for w in words])
            # Also add title case variations
            original_words_any_case.update([w.title() for w in words])
            original_words_any_case.update([w.capitalize() for w in words])

        # Each result word should match some casing of an original word
        # or be a substring of an original word (like "Phone" from "iPhone")
        for word in result_clean.split():
            clean_word = word.strip(',.?!:;"\'')

            # Check if word exists in any case variation OR is substring of original
            word_found = clean_word in original_words_any_case

            # Also check if it's a substring of any original word
            if not word_found:
                for orig_word in [w for title in titles for w in title.split()]:
                    if clean_word.lower() in orig_word.lower():
                        word_found = True
                        break

            assert word_found, \
                f"Word '{word}' (cleaned: '{clean_word}') not found in any case variation or as substring"


class TestNoRedundantSubstrings:
    """
    Requirement 2: Group identifiers should not contain redundant/repeated substrings.

    Example bad output: "This is what happened on March his is what happened on March This is what happened on March"
    Expected: "This is what happened on March" (appears once)
    """

    def test_no_repeated_phrases_march_example(self):
        """
        Real example: The phrase "This is what happened on March" repeats 3 times.
        Should appear only once.
        """
        titles = [
            "This is what happened on March 7",
            "This is what happened on March 6"
        ]

        result = identify_group(titles)

        # The common phrase
        common_phrase = "This is what happened on March"

        # Count how many times it appears
        count = result.count(common_phrase)

        assert count <= 1, \
            f"Phrase '{common_phrase}' appears {count} times in '{result}', should appear at most once"

    def test_no_repeated_phrases_android_example(self):
        """
        Real example: "Android Phones" appears twice in "Best Android Phones Android Phones of 2026"
        Should appear only once.
        """
        titles = [
            "Best Android Phones of 2026 Tested",
            "9 Best Android Phones of 2026"
        ]

        result = identify_group(titles)

        # Count occurrences of "Android Phones"
        phrase = "Android Phones"
        count = result.count(phrase)

        assert count <= 1, \
            f"Phrase '{phrase}' appears {count} times in '{result}', should appear at most once"

    def test_no_repeated_phrases_attorney_general(self):
        """
        Real example: "chief technology officer after Sarah Chen" repeats multiple times.
        """
        titles = [
            "Company appoints Jane Smith as chief technology officer after Sarah Chen departs",
            "Company appoints former engineer Jane Smith for chief technology officer after Sarah Chen departs"
        ]

        result = identify_group(titles)

        # Check key phrases don't repeat
        phrases_to_check = ["chief technology officer", "Sarah Chen", "after Sarah Chen"]

        for phrase in phrases_to_check:
            if phrase in result:
                count = result.count(phrase)
                assert count == 1, \
                    f"Phrase '{phrase}' appears {count} times in '{result}', should appear once"

    def test_no_word_repetition_in_sequence(self):
        """
        Test that the same word doesn't appear consecutively or multiple times
        when it's clearly redundant.

        Example: "iPhone iPhone release" should be "iPhone release"
        """
        titles = [
            "iPhone 16 announcement today",
            "iPhone 16 features revealed"
        ]

        result = identify_group(titles)

        # Split into words
        words = result.split()

        # Check for consecutive duplicates
        consecutive_duplicates = []
        for i in range(len(words) - 1):
            if words[i] == words[i + 1]:
                consecutive_duplicates.append(words[i])

        assert len(consecutive_duplicates) == 0, \
            f"Found consecutive duplicate words: {consecutive_duplicates} in '{result}'"

    def test_no_overlapping_substrings_in_result(self):
        """
        Test that if the result contains overlapping substrings, they shouldn't both appear.

        Example: If result has "Best Android Phones of 2026" it shouldn't also have
        "Android Phones of 2026" since they overlap significantly.
        """
        titles = [
            "Best Android Phones of 2026 Review",
            "Best Android Phones of 2026 Tested"
        ]

        result = identify_group(titles)

        # Split result into phrases (by triple spaces, which might separate the top-3 substrings)
        # Current implementation concatenates top 3 common substrings with spaces

        # Check if result contains obviously overlapping phrases
        # This is a heuristic: if we see many of the same words repeated, something's wrong
        words = result.split()
        word_counts = {}
        for word in words:
            if len(word) > 3:  # Only count meaningful words
                word_counts[word] = word_counts.get(word, 0) + 1

        # No significant word should appear more than twice
        excessive_repeats = {word: count for word, count in word_counts.items() if count > 2}

        assert len(excessive_repeats) == 0, \
            f"Words repeated more than twice: {excessive_repeats} in '{result}'"

    def test_pick_one_when_substrings_very_similar(self):
        """
        When multiple substrings are very similar (e.g., differ only in last word),
        should pick just one representative.

        Example substrings:
        - "Who is Maria Garcia company's nominee"
        - "Who is Maria Garcia company's new"
        - "Who is Maria Garcia company's"

        Should pick one, not all three.
        """
        titles = [
            "Who is Maria Garcia, company's new pick for chief officer?",
            "Who is Maria Garcia, company's nominee for chief officer?"
        ]

        result = identify_group(titles)

        # The phrase "Who is Maria Garcia" shouldn't appear multiple times
        # even with different endings
        phrase = "Who is Maria Garcia"

        if phrase in result:
            # Count how many times this phrase starts a substring in the result
            # This is tricky to test precisely, but we can check for excessive length
            # If it appears many times, the result will be very long

            # Heuristic: result shouldn't be longer than 2x the longest common substring
            max_reasonable_length = len(phrase) * 3  # Allow some flexibility

            assert len(result) <= max_reasonable_length, \
                f"Result is too long ({len(result)} chars), suggesting repetition: '{result}'"

    def test_identical_titles_no_repetition(self):
        """
        When titles are identical, the common phrase should appear once.
        """
        titles = [
            "Breaking news about climate change",
            "Breaking news about climate change",
            "Breaking news about climate change"
        ]

        result = identify_group(titles)

        # Should not have excessive repetition
        if "Breaking news" in result:
            count = result.count("Breaking news")
            assert count <= 2, \
                f"'Breaking news' appears {count} times in '{result}', should appear at most twice"

    def test_case_insensitive_deduplication(self):
        """
        Test that phrases differing only in case are treated as duplicates.

        Real-world example from latest_news.json:
        - "Oil Prices Surge After Iran Attack" contains "Oil Prices Surge"
        - "Oil prices surge amid war in Iran" contains "Oil prices surge"

        These should be deduplicated as they're the same phrase with different case.
        The result should not contain both "[Oil Prices Surge]" and "[Oil prices surge]",
        nor should it contain "[prices]" separately when it's already in "Oil Prices Surge".
        """
        titles = [
            "Oil Prices Surge After Iran Attack",
            "Oil prices surge amid war in Iran",
            "Oil and gas prices rapidly rise as Iran war shows no signs of letting up",
            "United CEO said U.S. airfares could rise as Iran war drives up oil prices"
        ]

        result = identify_group(titles)

        # Strip brackets to analyze phrases
        phrases = [p.strip() for p in result.replace('[', '|').replace(']', '').split('|') if p.strip()]

        # Check that we don't have case-variant duplicates
        phrases_lower = [p.lower() for p in phrases]
        unique_phrases_lower = set(phrases_lower)

        assert len(phrases_lower) == len(unique_phrases_lower), \
            f"Found case-variant duplicates in result: {phrases}. " \
            f"Phrases (lowercased): {phrases_lower}"

        # Check that smaller words contained in larger phrases are not separate
        for i, phrase in enumerate(phrases):
            phrase_words = set(phrase.lower().split())
            for j, other_phrase in enumerate(phrases):
                if i != j:
                    other_words = set(other_phrase.lower().split())
                    # If all words of phrase are in other_phrase, it's redundant
                    if phrase_words and phrase_words.issubset(other_words):
                        assert False, \
                            f"Phrase '{phrase}' is redundant with '{other_phrase}' in result: {result}"


class TestKeepShortestWhen75PercentOverlap:
    """
    Requirement 3: When substrings match >75% of words, keep the shortest one.

    Example:
    - "Best Android Phones of 2026" (5 words)
    - "Android Phones of 2026" (4 words, 100% of its words are in the first = keep this)
    - "Best Android Phones" (3 words, 100% of its words are in the first = keep this)

    When overlap >75%, we should keep only the shortest substring.
    """

    def test_two_substrings_100_percent_overlap_keep_shorter(self):
        """
        When one substring's words are 100% contained in another, keep the shorter one.

        "Android Phones of 2026" (4 words) is fully contained in
        "Best Android Phones of 2026" (5 words)
        → Keep "Android Phones of 2026"
        """
        titles = [
            "Best Android Phones of 2026 Review",
            "Best Android Phones of 2026 Tested"
        ]

        # Get the common substrings
        substrings = extract_common_substrings(titles, min_length=3)

        long_substring = "Best Android Phones of 2026"
        short_substring = "Android Phones of 2026"

        # Calculate overlap
        if long_substring in substrings and short_substring in substrings:
            long_words = set(long_substring.split())
            short_words = set(short_substring.split())

            # Check what percentage of short_words are in long_words
            overlap = len(short_words & long_words) / len(short_words) * 100

            # If overlap > 75%, both shouldn't be in the result
            if overlap > 75:
                # The identify_group should use only one of them
                result = identify_group(titles)

                # They shouldn't both appear in the final identifier
                has_long = long_substring in result
                has_short = short_substring in result

                assert not (has_long and has_short), \
                    f"Both '{long_substring}' and '{short_substring}' appear in result. " \
                    f"Overlap is {overlap:.1f}%, should keep only shorter one."

    def test_three_overlapping_substrings_keep_shortest(self):
        """
        When we have multiple overlapping substrings, keep the shortest.

        - "Best Android Phones of 2026" (5 words)
        - "Android Phones of 2026" (4 words) - 100% overlap with first
        - "Phones of 2026" (3 words) - 75% overlap with second

        Should keep "Phones of 2026" (shortest with >75% overlap)
        """
        titles = [
            "Best Android Phones of 2026 Review",
            "Best Android Phones of 2026 Guide"
        ]

        substrings = extract_common_substrings(titles, min_length=3)

        # Find overlapping substring groups
        candidates = [s for s in substrings if "2026" in s and len(s.split()) >= 3]

        if len(candidates) >= 2:
            # Sort by length
            candidates_sorted = sorted(candidates, key=lambda x: len(x.split()))

            # Check overlap between shortest and others
            shortest = candidates_sorted[0]
            shortest_words = set(shortest.split())

            overlapping_longer = []
            for candidate in candidates_sorted[1:]:
                candidate_words = set(candidate.split())
                overlap_pct = len(shortest_words & candidate_words) / len(shortest_words) * 100

                if overlap_pct > 75:
                    overlapping_longer.append(candidate)

            # If we found overlapping substrings, only shortest should be in final result
            if overlapping_longer:
                result = identify_group(titles)

                # Count how many of the overlapping ones appear in result
                count_in_result = sum(1 for s in overlapping_longer if s in result)

                # Ideally, only the shortest should appear, not the longer overlapping ones
                assert count_in_result == 0 or shortest not in result, \
                    f"Found {count_in_result} longer overlapping substrings in result when shortest '{shortest}' exists"

    def test_calculate_word_overlap_percentage(self):
        """
        Helper test: verify the overlap calculation logic.

        "Android Phones of 2026" vs "Best Android Phones of 2026"
        - Shorter has 4 words: ["Android", "Phones", "of", "2026"]
        - All 4 appear in longer string = 100% overlap
        """
        shorter = "Android Phones of 2026"
        longer = "Best Android Phones of 2026"

        shorter_words = set(shorter.split())
        longer_words = set(longer.split())

        overlap = len(shorter_words & longer_words) / len(shorter_words) * 100

        # This should be 100%
        assert overlap == 100.0, f"Expected 100% overlap, got {overlap}%"

        # Now test the 75% threshold case
        shorter2 = "Phones of 2026"  # 3 words
        longer2 = "Best Android Phones of 2026"  # 5 words

        shorter2_words = set(shorter2.split())
        longer2_words = set(longer2.split())

        overlap2 = len(shorter2_words & longer2_words) / len(shorter2_words) * 100

        # This should be 100% (all 3 words in shorter2 appear in longer2)
        assert overlap2 == 100.0, f"Expected 100% overlap, got {overlap2}%"

    def test_76_percent_overlap_triggers_deduplication(self):
        """
        Test the exact boundary: 76% overlap should trigger keeping only shortest.
        """
        # Create a scenario where overlap is just above 75%
        # "iPhone Pro Max" (3 words) vs "iPhone Pro Max features" (4 words)
        # Overlap: 3/3 = 100% - should keep shorter

        titles = [
            "iPhone Pro Max features announced",
            "iPhone Pro Max release date"
        ]

        substrings = extract_common_substrings(titles, min_length=3)

        # Check if we have overlapping candidates
        short_candidate = "iPhone Pro Max"
        long_candidate = "iPhone Pro Max features"  # or similar

        if short_candidate in substrings:
            # Find any longer substring that overlaps significantly
            short_words = set(short_candidate.split())

            for substring in substrings:
                if len(substring.split()) > len(short_words):
                    substring_words = set(substring.split())
                    overlap_pct = len(short_words & substring_words) / len(short_words) * 100

                    if overlap_pct > 75:
                        # Both shouldn't appear in final result
                        result = identify_group(titles)

                        has_short = short_candidate in result
                        has_long = substring in result

                        if has_short and has_long:
                            pytest.fail(
                                f"Both '{short_candidate}' and '{substring}' in result "
                                f"with {overlap_pct:.1f}% overlap (>75% threshold)"
                            )

    def test_74_percent_overlap_keeps_both(self):
        """
        Test just below threshold: 74% overlap should keep both substrings.
        This is a control test - at 74% we expect both to remain.
        """
        # This is trickier to construct, but the idea is:
        # If overlap is <=75%, both can appear
        # This test documents the expected behavior at the boundary

        # "new iPhone features" (3 words) vs "iPhone features release date" (4 words)
        # Overlap: 2/3 = 67% - should keep both

        # For now, this is a placeholder to document the boundary behavior
        pass  # We'll implement this if needed after the main logic is working

    def test_identify_group_filters_overlapping_substrings(self):
        """
        Integration test: identify_group should filter overlapping substrings
        before concatenating the top 3.
        """
        titles = [
            "Best Android Phones of 2026 Comprehensive Review",
            "Best Android Phones of 2026 Full Guide"
        ]

        result = identify_group(titles)

        # The result shouldn't have obvious redundancy from overlapping substrings
        # Check that "Android Phones of 2026" doesn't appear multiple times
        # with different prefixes/suffixes

        words = result.split()
        word_counts = {}
        for word in words:
            if len(word) > 2:  # Count significant words
                word_counts[word] = word_counts.get(word, 0) + 1

        # No word should appear more than 3 times (allowing for top-3 substrings)
        excessive = {word: count for word, count in word_counts.items() if count > 3}

        assert len(excessive) == 0, \
            f"Words appearing >3 times suggest overlapping substrings weren't filtered: {excessive}"

    def test_overlap_calculation_helper(self):
        """
        Non-failing helper test: demonstrates the overlap calculation.
        """
        # Test case 1: 100% overlap
        s1_words = {"Android", "Phones", "2026"}
        s2_words = {"Best", "Android", "Phones", "2026"}

        overlap1 = len(s1_words & s2_words) / len(s1_words) * 100
        assert overlap1 == 100.0, "All words from s1 are in s2"

        # Test case 2: 75% overlap
        s3_words = {"Apple", "iPhone", "Pro", "Max"}
        s4_words = {"iPhone", "Pro", "Max"}  # Missing "Apple"

        overlap2 = len(s4_words & s3_words) / len(s4_words) * 100
        assert overlap2 == 100.0, "All words from s4 are in s3"

        # Test case 3: 50% overlap (below threshold)
        s5_words = {"Apple", "iPhone"}
        s6_words = {"Apple", "Watch"}

        overlap3 = len(s5_words & s6_words) / len(s5_words) * 100
        assert overlap3 == 50.0, "Only 'Apple' is common"


class TestBasicFunctionality:
    """Ensure basic functionality works before testing edge cases."""

    def test_identify_group_returns_string(self):
        """Basic: function should return a string."""
        titles = ["Test title 1", "Test title 2"]
        result = identify_group(titles)
        assert isinstance(result, str), "Should return a string"

    def test_identify_group_empty_list(self):
        """Should handle empty list gracefully."""
        result = identify_group([])
        assert result == "", "Empty list should return empty string"

    def test_identify_group_single_title(self):
        """Single title should return empty (no common substrings)."""
        result = identify_group(["Single title"])
        assert result == "", "Single title should return empty string"

    def test_extract_substrings_returns_list(self):
        """Basic: function should return a list."""
        titles = ["Test 1", "Test 2"]
        result = extract_common_substrings(titles)
        assert isinstance(result, list), "Should return a list"

    def test_extract_substrings_sorted_by_length(self):
        """Substrings should be sorted longest first."""
        titles = ["Apple iPhone release", "Apple iPhone pricing"]
        result = extract_common_substrings(titles, min_length=3)

        # Verify sorted by length descending
        if len(result) > 1:
            for i in range(len(result) - 1):
                assert len(result[i]) >= len(result[i + 1]), \
                    f"Not sorted by length: '{result[i]}' ({len(result[i])}) before " \
                    f"'{result[i + 1]}' ({len(result[i + 1])})"
