"""Tests for news group ranking/sorting logic."""

import pytest


class TestGroupRanking:
    """Test that news groups are ranked according to priority rules."""

    def test_ranking_rules_from_latest_news(self):
        """
        Test ranking using a sample structure from latest_news.json.

        Ranking rules (in priority order):
        1. Multi-phrase groups (2+ top-level phrases) rank higher than single-phrase groups
        2. Within each category, more sub-groupings rank higher
        3. Within each category, more total news items rank higher
        4. Single-phrase groups with 1 sub-group and 2 news go to the very bottom
        """
        # Sample data representing different group structures
        sample_groups = {
            # SINGLE-PHRASE GROUPS (should be at bottom)
            "[Berkshire Hathaway]": {
                "[Berkshire Hathaway]": {
                    "news1": {"title": "News 1"},
                    "news2": {"title": "News 2"}
                }
            },
            "[Lifts PT]": {
                "[Lifts PT]": {
                    "news1": {"title": "News 1"},
                    "news2": {"title": "News 2"}
                }
            },
            "[Novo Nordisk]": {
                "[Novo Nordisk]": {
                    "news1": {"title": "News 1"},
                    "news2": {"title": "News 2"},
                    "news3": {"title": "News 3"}
                }
            },

            # MULTI-PHRASE GROUPS (should be at top)
            "[war impedes production] [Iran War] [Oil prices]": {
                "[Oil Prices Surge] [barrel]": {
                    "news1": {"title": "News 1"},
                    "news2": {"title": "News 2"},
                    "news3": {"title": "News 3"}
                },
                "[Gas Prices]": {
                    "news4": {"title": "News 4"},
                    "news5": {"title": "News 5"}
                },
                "[Oil spike]": {
                    "news6": {"title": "News 6"},
                    "news7": {"title": "News 7"}
                }
            },
            "[enjoy] [retirement]": {
                "[retirement]": {
                    "news1": {"title": "News 1"},
                    "news2": {"title": "News 2"}
                },
                "[enjoy]": {
                    "news3": {"title": "News 3"},
                    "news4": {"title": "News 4"}
                }
            },
            "[banks] [crypto]": {
                "[crypto]": {
                    "news1": {"title": "News 1"},
                    "news2": {"title": "News 2"}
                }
            },
            "[markets] [calm] [prices]": {
                "[markets]": {
                    "news1": {"title": "News 1"},
                    "news2": {"title": "News 2"}
                },
                "[calm]": {
                    "news3": {"title": "News 3"},
                    "news4": {"title": "News 4"}
                }
            }
        }

        # Import the ranking function (to be implemented)
        from newvelles.models.grouping import rank_news_groups

        ranked = rank_news_groups(sample_groups)
        ranked_keys = list(ranked.keys())

        # Verify multi-phrase groups come before single-phrase groups
        multi_phrase_indices = []
        single_phrase_indices = []

        for i, key in enumerate(ranked_keys):
            phrase_count = len([p.strip() for p in key.replace('[', '|').replace(']', '').split('|') if p.strip()])
            if phrase_count > 1:
                multi_phrase_indices.append(i)
            else:
                single_phrase_indices.append(i)

        # All multi-phrase groups should come before all single-phrase groups
        if multi_phrase_indices and single_phrase_indices:
            assert max(multi_phrase_indices) < min(single_phrase_indices), \
                "Multi-phrase groups should rank higher than single-phrase groups"

        # Among multi-phrase groups, verify sorting by sub-groupings then news count
        multi_phrase_groups = [ranked_keys[i] for i in multi_phrase_indices]
        for i in range(len(multi_phrase_groups) - 1):
            current = multi_phrase_groups[i]
            next_group = multi_phrase_groups[i + 1]

            current_subgroups = len(sample_groups[current])
            next_subgroups = len(sample_groups[next_group])

            current_news = sum(len(articles) for articles in sample_groups[current].values())
            next_news = sum(len(articles) for articles in sample_groups[next_group].values())

            # Current should have >= sub-groupings or >= news than next
            # (Higher priority items come first)
            assert current_subgroups >= next_subgroups or \
                   (current_subgroups == next_subgroups and current_news >= next_news), \
                   f"Group '{current}' should rank higher than '{next_group}' based on sub-groupings/news count"

        # Among single-phrase groups, 1 sub-group + 2 news should be at the very bottom
        single_phrase_groups = [ranked_keys[i] for i in single_phrase_indices]
        if len(single_phrase_groups) > 1:
            last_group = single_phrase_groups[-1]
            last_subgroups = len(sample_groups[last_group])
            last_news = sum(len(articles) for articles in sample_groups[last_group].values())

            # The last group should have the minimal structure (1 sub-group, 2 news)
            # OR be tied with others of the same structure
            for group in single_phrase_groups[:-1]:
                group_subgroups = len(sample_groups[group])
                group_news = sum(len(articles) for articles in sample_groups[group].values())

                # Last group should have <= sub-groupings and <= news
                assert last_subgroups <= group_subgroups or \
                       (last_subgroups == group_subgroups and last_news <= group_news), \
                       f"Group with minimal structure should be at bottom"

    def test_expected_order_from_sample(self):
        """
        Test with specific expected order based on ranking rules.
        """
        sample_groups = {
            "[A]": {  # 1 phrase, 1 sub, 2 news -> very bottom
                "[A]": {
                    "n1": {"title": "1"},
                    "n2": {"title": "2"}
                }
            },
            "[B]": {  # 1 phrase, 1 sub, 3 news -> bottom but above [A]
                "[B]": {
                    "n1": {"title": "1"},
                    "n2": {"title": "2"},
                    "n3": {"title": "3"}
                }
            },
            "[X] [Y]": {  # 2 phrases, 1 sub, 2 news -> top category
                "[X]": {
                    "n1": {"title": "1"},
                    "n2": {"title": "2"}
                }
            },
            "[P] [Q] [R]": {  # 3 phrases, 2 subs, 6 news -> highest
                "[P]": {
                    "n1": {"title": "1"},
                    "n2": {"title": "2"},
                    "n3": {"title": "3"}
                },
                "[Q]": {
                    "n4": {"title": "4"},
                    "n5": {"title": "5"},
                    "n6": {"title": "6"}
                }
            },
            "[M] [N]": {  # 2 phrases, 2 subs, 4 news -> second highest
                "[M]": {
                    "n1": {"title": "1"},
                    "n2": {"title": "2"}
                },
                "[N]": {
                    "n3": {"title": "3"},
                    "n4": {"title": "4"}
                }
            }
        }

        from newvelles.models.grouping import rank_news_groups

        ranked = rank_news_groups(sample_groups)
        ranked_keys = list(ranked.keys())

        # Expected order (highest priority first):
        # 1. [P] [Q] [R] - 3 phrases, 2 subs, 6 news
        # 2. [M] [N] - 2 phrases, 2 subs, 4 news
        # 3. [X] [Y] - 2 phrases, 1 sub, 2 news
        # 4. [B] - 1 phrase, 1 sub, 3 news
        # 5. [A] - 1 phrase, 1 sub, 2 news (very bottom)

        expected_order = [
            "[P] [Q] [R]",
            "[M] [N]",
            "[X] [Y]",
            "[B]",
            "[A]"
        ]

        assert ranked_keys == expected_order, \
            f"Expected order: {expected_order}\nActual order: {ranked_keys}"

    def test_single_word_phrases_rank_lowest(self):
        """
        Test that single-phrase groups with only 1 word rank lower than
        single-phrase groups with 2+ words.

        Ranking rules for single-phrase groups:
        1. Multi-word phrases (2+ words) rank higher than single-word phrases
        2. Among multi-word phrases: more sub-groups > more news
        3. Among single-word phrases: more sub-groups > more news
        """
        sample_groups = {
            # MULTI-PHRASE GROUPS (should be at top)
            "[X] [Y]": {
                "[X]": {
                    "n1": {"title": "1"},
                    "n2": {"title": "2"}
                }
            },

            # SINGLE-PHRASE MULTI-WORD GROUPS (middle tier)
            "[Berkshire Hathaway]": {  # 2 words, 1 sub, 2 news
                "[Berkshire Hathaway]": {
                    "news1": {"title": "News 1"},
                    "news2": {"title": "News 2"}
                }
            },
            "[housing vouchers]": {  # 2 words, 1 sub, 2 news
                "[housing vouchers]": {
                    "news1": {"title": "News 1"},
                    "news2": {"title": "News 2"}
                }
            },
            "[Novo Nordisk]": {  # 2 words, 1 sub, 3 news (should rank higher due to more news)
                "[Novo Nordisk]": {
                    "news1": {"title": "News 1"},
                    "news2": {"title": "News 2"},
                    "news3": {"title": "News 3"}
                }
            },

            # SINGLE-PHRASE SINGLE-WORD GROUPS (should be at very bottom)
            "[Sleep]": {  # 1 word, 1 sub, 2 news
                "[Sleep]": {
                    "news1": {"title": "News 1"},
                    "news2": {"title": "News 2"}
                }
            },
            "[Chicago]": {  # 1 word, 1 sub, 2 news
                "[Chicago]": {
                    "news1": {"title": "News 1"},
                    "news2": {"title": "News 2"}
                }
            },
            "[de]": {  # 1 word, 1 sub, 3 news (should rank higher than other single-word due to more news)
                "[de]": {
                    "news1": {"title": "News 1"},
                    "news2": {"title": "News 2"},
                    "news3": {"title": "News 3"}
                }
            }
        }

        from newvelles.models.grouping import rank_news_groups

        ranked = rank_news_groups(sample_groups)
        ranked_keys = list(ranked.keys())

        # Verify structure: Multi-phrase > Multi-word single-phrase > Single-word single-phrase
        multi_phrase_groups = []
        multi_word_single_phrase = []
        single_word_single_phrase = []

        for key in ranked_keys:
            phrase_count = len([p.strip() for p in key.replace('[', '|').replace(']', '').split('|') if p.strip()])
            if phrase_count > 1:
                multi_phrase_groups.append(key)
            else:
                # Count words in the single phrase
                word_count = len(key.replace('[', '').replace(']', '').strip().split())
                if word_count == 1:
                    single_word_single_phrase.append(key)
                else:
                    multi_word_single_phrase.append(key)

        # Get indices for verification
        if multi_phrase_groups:
            max_multi_phrase_idx = ranked_keys.index(multi_phrase_groups[-1])
        else:
            max_multi_phrase_idx = -1

        if multi_word_single_phrase:
            min_multi_word_idx = ranked_keys.index(multi_word_single_phrase[0])
            max_multi_word_idx = ranked_keys.index(multi_word_single_phrase[-1])
        else:
            min_multi_word_idx = max_multi_word_idx = -1

        if single_word_single_phrase:
            min_single_word_idx = ranked_keys.index(single_word_single_phrase[0])
        else:
            min_single_word_idx = 999

        # Verify ordering: multi-phrase < multi-word single-phrase < single-word single-phrase
        if multi_phrase_groups and multi_word_single_phrase:
            assert max_multi_phrase_idx < min_multi_word_idx, \
                f"Multi-phrase groups should rank higher than multi-word single-phrase groups"

        if multi_word_single_phrase and single_word_single_phrase:
            assert max_multi_word_idx < min_single_word_idx, \
                f"Multi-word single-phrase groups should rank higher than single-word single-phrase groups. " \
                f"Multi-word groups: {multi_word_single_phrase}, Single-word groups: {single_word_single_phrase}"

        # Verify expected order structure
        # Position 0: Multi-phrase group
        assert ranked_keys[0] == "[X] [Y]", "Multi-phrase should be first"

        # Positions 1-3: Multi-word single-phrase (sorted by news count)
        assert ranked_keys[1] == "[Novo Nordisk]", "2-word with 3 news should be first among multi-word"
        # Berkshire Hathaway and housing vouchers are tied (2 words, 1 sub, 2 news)
        assert set(ranked_keys[2:4]) == {"[Berkshire Hathaway]", "[housing vouchers]"}, \
            "Both 2-word 2-news groups should be in positions 2-3"

        # Positions 4-6: Single-word single-phrase (sorted by news count, then alphabetically for ties)
        assert ranked_keys[4] == "[de]", "1-word with 3 news should be first among single-word"
        # Chicago and Sleep are tied (1 word, 1 sub, 2 news), order is non-deterministic
        assert set(ranked_keys[5:7]) == {"[Chicago]", "[Sleep]"}, \
            "Both 1-word 2-news groups should be in positions 5-6"
