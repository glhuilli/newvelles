"""Tests for newvelles.display.show module."""

import json
from io import StringIO
from unittest.mock import patch

import pytest

from newvelles.display.show import print_sorted_grouped_titles, print_viz


class TestPrintSortedGroupedTitles:
    """Test print_sorted_grouped_titles function."""

    @patch("builtins.print")
    def test_print_sorted_grouped_titles_basic(self, mock_print):
        """Test basic functionality of print_sorted_grouped_titles."""
        group_sentences = {
            1: ["First group sentence 1", "First group sentence 2"],
            2: [
                "Second group sentence 1",
                "Second group sentence 2",
                "Second group sentence 3",
            ],
        }

        print_sorted_grouped_titles(group_sentences)

        # Should print separators and sentences
        print_calls = [call[0][0] for call in mock_print.call_args_list]

        # Check for separators (asterisks)
        separator_calls = [call for call in print_calls if "*" in call]
        assert len(separator_calls) == 2  # One separator per group

        # Check that all sentences were printed
        sentence_calls = [call for call in print_calls if "sentence" in call]
        assert len(sentence_calls) == 5  # Total sentences across groups

    @patch("builtins.print")
    def test_print_sorted_grouped_titles_empty_dict(self, mock_print):
        """Test print_sorted_grouped_titles with empty dictionary."""
        group_sentences = {}

        print_sorted_grouped_titles(group_sentences)

        # Should not print anything
        mock_print.assert_not_called()

    @patch("builtins.print")
    def test_print_sorted_grouped_titles_empty_groups(self, mock_print):
        """Test print_sorted_grouped_titles with empty groups."""
        group_sentences = {1: [], 2: []}

        print_sorted_grouped_titles(group_sentences)

        # Should print separators but no sentences
        print_calls = [call[0][0] for call in mock_print.call_args_list]
        separator_calls = [call for call in print_calls if "*" in call]
        assert len(separator_calls) == 2  # One separator per group

        # No sentence calls
        sentence_calls = [call for call in print_calls if call != "*" * 50]
        assert len(sentence_calls) == 0

    @patch("builtins.print")
    def test_print_sorted_grouped_titles_single_group(self, mock_print):
        """Test print_sorted_grouped_titles with single group."""
        group_sentences = {1: ["Only sentence in group"]}

        print_sorted_grouped_titles(group_sentences)

        # Should print one separator and one sentence
        print_calls = [call[0][0] for call in mock_print.call_args_list]
        assert "*" * 50 in print_calls
        assert "Only sentence in group" in print_calls

    @patch("builtins.print")
    def test_print_sorted_grouped_titles_special_characters(self, mock_print):
        """Test print_sorted_grouped_titles with special characters."""
        group_sentences = {
            1: ["Sentence with émojis 🚀", "Spéciâl châractërs", "Numbers: 123"]
        }

        print_sorted_grouped_titles(group_sentences)

        # Should handle special characters correctly
        print_calls = [call[0][0] for call in mock_print.call_args_list]
        assert "Sentence with émojis 🚀" in print_calls
        assert "Spéciâl châractërs" in print_calls
        assert "Numbers: 123" in print_calls

    @patch("builtins.print")
    def test_print_sorted_grouped_titles_long_sentences(self, mock_print):
        """Test print_sorted_grouped_titles with very long sentences."""
        long_sentence = "This is a very long sentence " * 20
        group_sentences = {1: [long_sentence]}

        print_sorted_grouped_titles(group_sentences)

        # Should handle long sentences without issues
        print_calls = [call[0][0] for call in mock_print.call_args_list]
        assert long_sentence in print_calls


class TestPrintViz:
    """Test print_viz function."""

    @patch("builtins.print")
    def test_print_viz_basic(self, mock_print):
        """Test basic functionality of print_viz."""
        visualization = {
            "group1": {
                "subgroup1": {
                    "article1": {"title": "Test Article", "link": "https://example.com"}
                }
            }
        }

        print_viz(visualization)

        # Should print JSON representation
        mock_print.assert_called_once()
        printed_content = mock_print.call_args[0][0]

        # Should be valid JSON format with indentation
        assert "{\n" in printed_content  # JSON with newlines
        assert '"group1"' in printed_content
        assert '"Test Article"' in printed_content

    @patch("builtins.print")
    def test_print_viz_empty_dict(self, mock_print):
        """Test print_viz with empty dictionary."""
        visualization = {}

        print_viz(visualization)

        # Should print empty JSON object
        mock_print.assert_called_once()
        printed_content = mock_print.call_args[0][0]
        assert printed_content.strip() == "{}"

    @patch("builtins.print")
    def test_print_viz_complex_structure(self, mock_print):
        """Test print_viz with complex nested structure."""
        visualization = {
            "tech_news": {
                "apple": {
                    "iPhone 15 released": {
                        "title": "iPhone 15 released",
                        "link": "https://apple.com/iphone",
                        "published": "2025-01-16",
                        "source": "Apple",
                    },
                    "iPhone 15 specs": {
                        "title": "iPhone 15 specifications",
                        "link": "https://apple.com/specs",
                        "published": "2025-01-16",
                        "source": "TechCrunch",
                    },
                },
                "tesla": {
                    "Tesla earnings": {
                        "title": "Tesla Q4 earnings",
                        "link": "https://tesla.com/earnings",
                        "published": "2025-01-15",
                        "source": "Reuters",
                    }
                },
            },
            "business_news": {
                "markets": {
                    "Stock market update": {
                        "title": "Markets close higher",
                        "link": "https://markets.com/update",
                        "published": "2025-01-16",
                        "source": "Bloomberg",
                    }
                }
            },
        }

        print_viz(visualization)

        # Should print complex JSON structure
        mock_print.assert_called_once()
        printed_content = mock_print.call_args[0][0]

        # Verify it's properly formatted JSON
        parsed_json = json.loads(printed_content)
        assert parsed_json == visualization

        # Check indentation is applied
        assert "  " in printed_content  # Should have 2-space indentation

    @patch("builtins.print")
    def test_print_viz_special_characters(self, mock_print):
        """Test print_viz with special characters."""
        visualization = {
            "news_émojis": {
                "spéciâl": {
                    "artíclé with ñ": {
                        "title": "Spëcîål chäracters 🚀",
                        "link": "https://example.com/spëcîål",
                        "published": "2025-01-16",
                        "source": "Tëst Sõurce",
                    }
                }
            }
        }

        print_viz(visualization)

        # Should handle special characters in JSON
        mock_print.assert_called_once()
        printed_content = mock_print.call_args[0][0]

        # Verify special characters are preserved (may be Unicode escaped)
        assert "émojis" in printed_content or "\\u00e9mojis" in printed_content
        assert (
            "Spëcîål chäracters 🚀" in printed_content or "Sp\\u00eb" in printed_content
        )
        assert "ñ" in printed_content or "\\u00f1" in printed_content

    @patch("builtins.print")
    def test_print_viz_numeric_values(self, mock_print):
        """Test print_viz with numeric values."""
        visualization = {
            "stats": {
                "metrics": {
                    "article_count": 42,
                    "avg_score": 3.14159,
                    "is_active": True,
                    "null_value": None,
                }
            }
        }

        print_viz(visualization)

        # Should handle different data types in JSON
        mock_print.assert_called_once()
        printed_content = mock_print.call_args[0][0]

        # Verify different types are serialized correctly
        assert "42" in printed_content
        assert "3.14159" in printed_content
        assert "true" in printed_content  # JSON boolean
        assert "null" in printed_content  # JSON null

    @patch("builtins.print")
    @patch("newvelles.display.show.json.dumps")
    def test_print_viz_json_formatting(self, mock_json_dumps, mock_print):
        """Test that print_viz uses correct JSON formatting."""
        visualization = {"test": "data"}
        mock_json_dumps.return_value = '{"test": "data"}'

        print_viz(visualization)

        # Should call json.dumps with indent=2
        mock_json_dumps.assert_called_once_with(visualization, indent=2)
        mock_print.assert_called_once_with('{"test": "data"}')

    @patch("builtins.print")
    def test_print_viz_large_data(self, mock_print):
        """Test print_viz with large dataset."""
        # Create large visualization data
        visualization = {}
        for i in range(100):
            group_name = f"group_{i}"
            visualization[group_name] = {}
            for j in range(10):
                subgroup_name = f"subgroup_{j}"
                visualization[group_name][subgroup_name] = {}
                for k in range(5):
                    article_name = f"article_{k}"
                    visualization[group_name][subgroup_name][article_name] = {
                        "title": f"Article {k} in {subgroup_name}",
                        "link": f"https://example.com/{i}/{j}/{k}",
                        "published": "2025-01-16",
                        "source": "Test Source",
                    }

        print_viz(visualization)

        # Should handle large datasets without issues
        mock_print.assert_called_once()
        printed_content = mock_print.call_args[0][0]

        # Verify it's still valid JSON
        parsed_json = json.loads(printed_content)
        assert len(parsed_json) == 100
