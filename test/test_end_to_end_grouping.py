"""
End-to-end integration tests for group identifier generation.

These tests use real-world examples from latest_news.json to verify that the
grouping algorithm produces the expected group identifiers for actual news articles.
"""

import pytest

from newvelles.models.grouping import identify_group


class TestEndToEndGrouping:
    """
    Integration tests using actual news article groupings from production data.

    Each test verifies that a set of real titles produces the expected group identifier.
    These tests serve as regression tests and documentation of expected behavior.
    """

    def test_oslo_embassy_explosion(self):
        """
        Test: Oslo embassy explosion news group.

        Real-world example of multiple news outlets covering the same event
        with different phrasings.

        Note: "Police Investigate Explosion Embassy" and "Norway investigate explosion Embassy"
        share 75% of their words, so with case-insensitive overlap filtering at 50% threshold,
        only one is kept.
        """
        titles = [
            "Oslo Police Investigate Explosion Outside U.S. Embassy",
            "Police in Norway investigate explosion outside US Embassy in Oslo",
            "Police investigate after explosion outside U.S. Embassy in Norway",
            "Police in Norway investigate an explosion outside the U.S. Embassy in Oslo",
            "Police investigate a potential explosion outside the US Embassy in Oslo",
        ]

        result = identify_group(titles)
        expected = "[Norway investigate explosion Embassy] [Police] [Oslo]"

        assert result == expected, \
            f"Oslo embassy explosion group identifier mismatch.\nExpected: {expected}\nActual: {result}"

    def test_blood_moon_eclipse(self):
        """
        Test: Total lunar eclipse (blood moon) news group.

        Example of science/astronomy news coverage with consistent terminology.
        """
        titles = [
            "Photos: Blood Moon Total Lunar Eclipse 2026",
            "Total lunar eclipse will turn the moon 'blood' red. Here's how to watch",
        ]

        result = identify_group(titles)
        expected = "[Total Lunar Eclipse] [Blood] [Moon]"

        assert result == expected, \
            f"Blood moon eclipse group identifier mismatch.\nExpected: {expected}\nActual: {result}"

    def test_oil_prices_iran(self):
        """
        Test: Oil prices surge due to Iran news group.

        Example of economic/energy news with clear topical focus.
        """
        titles = [
            "Oil Prices Surge After Iran Attack",
            "Oil prices surge amid war in Iran",
        ]

        result = identify_group(titles)
        expected = "[Oil Prices Surge] [Iran]"

        assert result == expected, \
            f"Oil prices Iran group identifier mismatch.\nExpected: {expected}\nActual: {result}"

    def test_generic_report(self):
        """
        Test: Generic report headlines.

        Example where titles are very vague/generic, resulting in minimal identifier.
        """
        titles = [
            "What to know about the report.",
            "What to know about the jobs report.",
        ]

        result = identify_group(titles)
        expected = "[report]"

        assert result == expected, \
            f"Generic report group identifier mismatch.\nExpected: {expected}\nActual: {result}"

    def test_daylight_saving_time_bc(self):
        """
        Test: British Columbia daylight saving time news group.

        Example with multiple related concepts: location, policy change, time.

        Note: With case-insensitive overlap filtering, "daylight saving time" (lowercase)
        and "Daylight" are treated as overlapping, so only standalone "Daylight" remains
        after "Saving Time Changing Clocks" is selected.
        """
        titles = [
            "British Columbia Moving to Permanent Daylight Saving Time, Changing Clocks for the Last Time Sunday",
            "British Columbia to make daylight saving time permanent",
            "Daylight saving time begins: Are we changing the clocks for the last time?",
        ]

        result = identify_group(titles)
        # Note: "Daylight" vs "daylight" case can vary due to dictionary ordering in Python
        expected1 = "[Saving Time Changing Clocks] [British Columbia] [Daylight]"
        expected2 = "[Saving Time Changing Clocks] [British Columbia] [daylight]"

        assert result in [expected1, expected2], \
            f"Daylight saving time BC group identifier mismatch.\nExpected: {expected1} or {expected2}\nActual: {result}"

    def test_generic_latest(self):
        """
        Test: Generic 'latest' update headlines.

        Example of very generic update headlines with minimal specific content.
        """
        titles = [
            "Here is the latest.",
            "Here's the latest.",
        ]

        result = identify_group(titles)
        expected = "[latest]"

        assert result == expected, \
            f"Generic latest group identifier mismatch.\nExpected: {expected}\nActual: {result}"

    def test_march_events(self):
        """
        Test: March date-specific event summaries.

        Example of recurring date-based summary headlines.
        """
        titles = [
            "This is what happened on March 7.",
            "This is what happened on March 6.",
        ]

        result = identify_group(titles)
        expected = "[happened March]"

        assert result == expected, \
            f"March events group identifier mismatch.\nExpected: {expected}\nActual: {result}"

    def test_nepal_election_rapper(self):
        """
        Test: Nepal election with ex-rapper candidate.

        Example of unique political story with distinctive elements.
        """
        titles = [
            "A new Nepali party, led by an ex-rapper, is set for a landslide win in parliamentary election",
            "A new Nepali party led by an ex-rapper is set for a landslide win in parliamentary election",
        ]

        result = identify_group(titles)
        expected = "[landslide win parliamentary election] [Nepali party led ex-rapper] [ex-rapper set landslide]"

        assert result == expected, \
            f"Nepal election rapper group identifier mismatch.\nExpected: {expected}\nActual: {result}"

    def test_china_us_relations(self):
        """
        Test: China-US relationship landmark year.

        Example of diplomatic/international relations news.
        """
        titles = [
            "China hopes 2026 will be a 'landmark year' for relationship with US",
            "China hopes 2026 will be a 'landmark year' for relationship with U.S.",
        ]

        result = identify_group(titles)
        expected = "[China hopes 2026 landmark] [landmark year relationship]"

        assert result == expected, \
            f"China US relations group identifier mismatch.\nExpected: {expected}\nActual: {result}"

    def test_peru_nightclub_bombing(self):
        """
        Test: Peru nightclub bombing news.

        Example of crime/violence news with specific casualties mentioned.
        """
        titles = [
            "A nightclub bombing in Peru injures 33, including minors, authorities say",
            "Bombing at nightclub in Peru injures 33, including minors, authorities say",
        ]

        result = identify_group(titles)
        expected = "[injures 33 including minors] [nightclub] [bombing]"

        assert result == expected, \
            f"Peru nightclub bombing group identifier mismatch.\nExpected: {expected}\nActual: {result}"

    def test_asus_monitor_deal(self):
        """
        Test: ASUS OLED gaming monitor deal.

        Example of tech product/deal news with consistent product naming.
        """
        titles = [
            "This Premium ASUS OLED Gaming Monitor Is Over $100 Off Right Now",
            "This ASUS OLED Gaming Monitor Is $200 Off Right Now",
        ]

        result = identify_group(titles)
        expected = "[ASUS OLED Gaming Monitor]"

        assert result == expected, \
            f"ASUS monitor deal group identifier mismatch.\nExpected: {expected}\nActual: {result}"

    def test_samsung_amazon_gift_card(self):
        """
        Test: Samsung products with Amazon gift card promotions.

        Example of product promotion news across different Samsung devices.
        """
        titles = [
            "You Can Get a $200 Amazon Gift Card With the New Samsung Galaxy S26 Ultra",
            "You Can Preorder the New Samsung Galaxy Buds 4 and Get Up to a $30 Amazon Gift Card",
        ]

        result = identify_group(titles)
        expected = "[Amazon Gift Card] [Samsung Galaxy]"

        assert result == expected, \
            f"Samsung Amazon gift card group identifier mismatch.\nExpected: {expected}\nActual: {result}"

    def test_face_the_nation(self):
        """
        Test: Face the Nation TV show episodes.

        Example of recurring TV show with date-based episodes.
        """
        titles = [
            "3/8: Face the Nation",
            "2/1: Face The Nation",
        ]

        result = identify_group(titles)
        expected = "[Face Nation]"

        assert result == expected, \
            f"Face the Nation group identifier mismatch.\nExpected: {expected}\nActual: {result}"

    def test_cbs_sunday_morning(self):
        """
        Test: CBS Sunday Morning TV show.

        Example of another recurring TV show.
        """
        titles = [
            "3/8: Sunday Morning",
            "This week on \"Sunday Morning\" (March 8)",
        ]

        result = identify_group(titles)
        expected = "[Sunday Morning]"

        assert result == expected, \
            f"CBS Sunday Morning group identifier mismatch.\nExpected: {expected}\nActual: {result}"

    def test_face_nation_transcripts(self):
        """
        Test: Face the Nation interview transcripts.

        Example of transcript-based news with consistent show and date format.
        """
        titles = [
            "Transcript: Sen. Tim Kaine on \"Face the Nation with Margaret Brennan,\" March 8, 2026",
            "Full transcript of \"Face the Nation with Margaret Brennan,\" March 8, 2026",
        ]

        result = identify_group(titles)
        expected = "[Brennan March 8 2026] [Face Nation Margaret Brennan] [Transcript]"

        assert result == expected, \
            f"Face Nation transcripts group identifier mismatch.\nExpected: {expected}\nActual: {result}"

    def test_energy_prices_temporary(self):
        """
        Test: Energy secretary comments on elevated energy prices.

        Example of political statement/quote-based news.

        Note: With case-insensitive overlap filtering, "Energy" is filtered when
        "elevated energy prices temporary" is selected, leaving just "secretary".
        """
        titles = [
            "Energy secretary says \"period of elevated energy prices\" will be temporary",
            "Energy Secretary Chris Wright says \"period of elevated energy prices\" will be temporary",
        ]

        result = identify_group(titles)
        expected = "[elevated energy prices temporary] [secretary] [period]"

        assert result == expected, \
            f"Energy prices temporary group identifier mismatch.\nExpected: {expected}\nActual: {result}"

    def test_tim_kaine_kristi_noem(self):
        """
        Test: Senator Tim Kaine regrets Kristi Noem vote.

        Example of political regret/mistake news.
        """
        titles = [
            "Sen. Tim Kaine says supporting Kristi Noem as DHS secretary was a \"big mistake\"",
            "Sen. Tim Kaine says he made a \"big mistake\" voting for Kristi Noem's confirmation",
        ]

        result = identify_group(titles)
        expected = "[Sen Tim Kaine] [big mistake] [Kristi]"

        assert result == expected, \
            f"Tim Kaine Kristi Noem group identifier mismatch.\nExpected: {expected}\nActual: {result}"

    def test_rfk_jr_sugary_drinks(self):
        """
        Test: RFK Jr. challenges coffee chains over sugary drinks.

        Example of health/food safety regulatory news.
        """
        titles = [
            "RFK Jr. challenges Dunkin' and Starbucks over sugary drinks",
            "RFK Jr. questions safety of sugary drinks at Dunkin'' and Starbucks",
        ]

        result = identify_group(titles)
        expected = "[RFK Jr] [Dunkin Starbucks] [sugary drinks]"

        assert result == expected, \
            f"RFK Jr sugary drinks group identifier mismatch.\nExpected: {expected}\nActual: {result}"

    def test_lloyd_blankfein_goldman_sachs(self):
        """
        Test: Former Goldman Sachs CEO interview.

        Example of business/finance interview news.
        """
        titles = [
            "Former Goldman Sachs CEO Lloyd Blankfein talks Wall Street crises",
            "Former Goldman Sachs CEO Lloyd Blankfein talks Wall Street crises, past and future",
        ]

        result = identify_group(titles)
        expected = "[Lloyd Blankfein talks Wall] [Goldman Sachs CEO Lloyd] [Wall Street crises]"

        assert result == expected, \
            f"Lloyd Blankfein Goldman Sachs group identifier mismatch.\nExpected: {expected}\nActual: {result}"

    def test_saturday_sessions_cory_wong(self):
        """
        Test: Saturday Sessions music performances.

        Example of recurring music segment with different songs.
        """
        titles = [
            "Saturday Sessions: Cory Wong performs \"Roses Fade\" with Devon Gilfillian",
            "Saturday Sessions: Cory Wong performs \"Blame It On the Moon\" with Devon Gilfillian",
        ]

        result = identify_group(titles)
        expected = "[Sessions Cory Wong performs] [Devon Gilfillian] [Saturday]"

        assert result == expected, \
            f"Saturday Sessions Cory Wong group identifier mismatch.\nExpected: {expected}\nActual: {result}"

    def test_marc_shaiman_composer(self):
        """
        Test: Marc Shaiman composer interview/profile.

        Example of entertainment/arts personality profile.
        """
        titles = [
            "Broadway, Hollywood composer Marc Shaiman on being a \"sore winner\"",
            "Broadway and Hollywood composer Marc Shaiman on his new memoir, and being a \"sore winner\"",
        ]

        result = identify_group(titles)
        expected = "[Broadway Hollywood composer Marc] [sore winner] [Shaiman]"

        assert result == expected, \
            f"Marc Shaiman composer group identifier mismatch.\nExpected: {expected}\nActual: {result}"

    def test_pixar_hoppers_vs_bride(self):
        """
        Test: Box office competition between Pixar and Warner Bros films.

        Example of entertainment/box office news with multiple films.
        """
        titles = [
            "Pixar's 'Hoppers' bounds to No. 1 as Warner Bros.' 'The Bride!' is on life support",
            "Pixar's 'Hoppers' bounds to No. 1 as Warner Bros.' 'The Bride!' is on life support",
            "Pixar's 'Hoppers' bounds to No. 1 as Warner Bros.' 'The Bride!' is on life support",
        ]

        result = identify_group(titles)
        expected = "[Pixars Hoppers bounds 1] [Bros Bride life support] [1 Warner Bros]"

        assert result == expected, \
            f"Pixar Hoppers group identifier mismatch.\nExpected: {expected}\nActual: {result}"

    def test_economy_rough_start(self):
        """
        Test: Global economy analysis for 2026.

        Example of economic analysis news.
        """
        titles = [
            "Global 'thriving' economy meets a rough start to 2026: What the latest numbers show",
            "Global 'thriving' economy meets a rough start to 2026: What the latest numbers show",
        ]

        result = identify_group(titles)
        expected = "[start 2026 latest numbers] [Global thriving economy meets] [meets rough start]"

        assert result == expected, \
            f"Economy group identifier mismatch.\nExpected: {expected}\nActual: {result}"

    def test_iran_president_statement(self):
        """
        Test: Iran president statement on US/Israel pressure.

        Example of international relations/diplomacy news with quotes.
        """
        titles = [
            "The Latest: Iran's president says nation 'will not bow' to pressure from US and Israel",
            "The Latest: Iran's president says nation 'will not bow' to pressure from US and Israel",
        ]

        result = identify_group(titles)
        expected = "[president nation bow pressure] [Latest Irans president] [Israel]"

        assert result == expected, \
            f"Iran president statement group identifier mismatch.\nExpected: {expected}\nActual: {result}"

    def test_corey_parker_death(self):
        """
        Test: Actor Corey Parker death announcement.

        Example of celebrity death news.
        """
        titles = [
            "Actor Corey Parker of 'Will & Grace,' other shows, dies: family",
            "Corey Parker of 'Will & Grace,' more dies: family",
        ]

        result = identify_group(titles)
        expected = "[Corey Parker & Grace] [Grace dies family]"

        assert result == expected, \
            f"Corey Parker death group identifier mismatch.\nExpected: {expected}\nActual: {result}"


class TestEdgeCases:
    """
    Additional edge case tests to ensure robustness.
    """

    def test_very_similar_titles(self):
        """
        Test that nearly identical titles produce clean identifiers without repetition.
        """
        titles = [
            "Breaking news: Major event happening now",
            "Breaking news: Major event is happening now",
            "Breaking news about major event happening now",
        ]

        result = identify_group(titles)

        # Should not have excessive repetition
        words = result.split()
        word_counts = {}
        for word in words:
            clean_word = word.strip('[]')
            if clean_word:
                word_counts[clean_word] = word_counts.get(clean_word, 0) + 1

        # No word should appear more than 3 times (allowing for top-3 substrings)
        excessive = {word: count for word, count in word_counts.items() if count > 3}
        assert len(excessive) == 0, \
            f"Found excessive word repetition: {excessive}"

    def test_empty_list(self):
        """
        Test that empty title list returns empty string.
        """
        result = identify_group([])
        assert result == "", "Empty list should return empty string"

    def test_single_title(self):
        """
        Test that single title returns empty string (no common substrings possible).
        """
        result = identify_group(["Single unique title"])
        assert result == "", "Single title should return empty string"

    def test_bracket_format_consistency(self):
        """
        Test that all outputs follow bracket format consistently.
        """
        titles = [
            "Apple announces new iPhone model",
            "Apple reveals iPhone specifications",
        ]

        result = identify_group(titles)

        # Should have brackets
        assert '[' in result and ']' in result, \
            f"Result should contain brackets: {result}"

        # Should have balanced brackets
        assert result.count('[') == result.count(']'), \
            f"Brackets should be balanced: {result}"

        # Each bracketed phrase should not be empty
        import re
        phrases = re.findall(r'\[([^\]]+)\]', result)
        for phrase in phrases:
            assert len(phrase.strip()) > 0, \
                f"Found empty bracketed phrase in: {result}"
