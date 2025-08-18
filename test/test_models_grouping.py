"""Tests for newvelles.models.grouping module."""

from unittest.mock import Mock, patch

import numpy as np
import pytest

from newvelles.feed import NewsEntry
from newvelles.models.grouping import (VISUALIZATION_VERSION, build_news_groups,
                                       build_visualization, build_visualization_lite,
                                       cluster_groups, extract_common_substrings,
                                       group_similar_titles, identify_group)


class TestGroupSimilarTitles:
    """Test group_similar_titles function."""

    @patch("newvelles.models.grouping.process_content")
    @patch("newvelles.models.grouping.TfidfVectorizer")
    @patch("newvelles.models.grouping.cosine_similarity")
    def test_group_similar_titles_basic(
        self, mock_cosine, mock_vectorizer, mock_process
    ):
        """Test basic functionality of group_similar_titles."""
        # Mock process_content to return simple tokens
        mock_process.side_effect = lambda x: x.lower().split()

        # Mock TfidfVectorizer
        mock_tfidf = Mock()
        mock_vectorizer.return_value = mock_tfidf
        mock_tfidf.fit_transform.return_value = "mocked_matrix"

        # Mock cosine_similarity to return a similarity matrix
        # where titles 0 and 1 are similar (>= 0.7)
        similarity_matrix = np.array(
            [
                [1.0, 0.8, 0.3],  # Title 0 similar to title 1
                [0.8, 1.0, 0.2],  # Title 1 similar to title 0
                [0.3, 0.2, 1.0],  # Title 2 not similar to others
            ]
        )
        mock_cosine.return_value = similarity_matrix

        titles = [
            "Apple launches new iPhone",
            "Apple announces iPhone release",
            "Tesla stock rises",
        ]

        result = group_similar_titles(titles, similarity_threshold=0.7)

        # Should group titles 0 and 1 together
        assert len(result) == 1
        assert set(result[0]) == {0, 1}

    @patch("newvelles.models.grouping.process_content")
    @patch("newvelles.models.grouping.TfidfVectorizer")
    @patch("newvelles.models.grouping.cosine_similarity")
    def test_group_similar_titles_no_groups(
        self, mock_cosine, mock_vectorizer, mock_process
    ):
        """Test when no titles are similar enough to group."""
        mock_process.side_effect = lambda x: x.lower().split()

        mock_tfidf = Mock()
        mock_vectorizer.return_value = mock_tfidf
        mock_tfidf.fit_transform.return_value = "mocked_matrix"

        # All titles have low similarity
        similarity_matrix = np.array(
            [[1.0, 0.3, 0.2], [0.3, 1.0, 0.4], [0.2, 0.4, 1.0]]
        )
        mock_cosine.return_value = similarity_matrix

        titles = [
            "Apple launches iPhone",
            "Tesla stock rises",
            "Biden announces policy",
        ]

        result = group_similar_titles(titles, similarity_threshold=0.7)

        # No groups should be formed
        assert len(result) == 0

    @patch("newvelles.models.grouping.process_content")
    @patch("newvelles.models.grouping.TfidfVectorizer")
    @patch("newvelles.models.grouping.cosine_similarity")
    def test_group_similar_titles_single_title(
        self, mock_cosine, mock_vectorizer, mock_process
    ):
        """Test with single title."""
        mock_process.side_effect = lambda x: x.lower().split()

        mock_tfidf = Mock()
        mock_vectorizer.return_value = mock_tfidf
        mock_tfidf.fit_transform.return_value = "mocked_matrix"

        similarity_matrix = np.array([[1.0]])
        mock_cosine.return_value = similarity_matrix

        titles = ["Single news title"]

        result = group_similar_titles(titles, similarity_threshold=0.7)

        # Single title cannot form a group
        assert len(result) == 0


class TestClusterGroups:
    """Test cluster_groups function."""

    @patch("newvelles.models.grouping.process_content")
    @patch("newvelles.models.grouping.TfidfVectorizer")
    @patch("newvelles.models.grouping.cosine_similarity")
    def test_cluster_groups_basic(self, mock_cosine, mock_vectorizer, mock_process):
        """Test basic functionality of cluster_groups."""
        mock_process.side_effect = lambda x: x.lower().split()

        mock_tfidf = Mock()
        mock_vectorizer.return_value = mock_tfidf
        mock_tfidf.fit_transform.return_value = "mocked_matrix"

        # Groups 0 and 1 are similar contexts
        similarity_matrix = np.array(
            [[1.0, 0.6, 0.1], [0.6, 1.0, 0.2], [0.1, 0.2, 1.0]]
        )
        mock_cosine.return_value = similarity_matrix

        groups = [[0, 1], [2, 3], [4, 5]]
        titles = [
            "Apple iPhone",
            "Apple iPad",
            "Tesla car",
            "Tesla truck",
            "Biden policy",
            "Biden speech",
        ]

        result = cluster_groups(groups, titles, context_similarity_threshold=0.5)

        # Groups 0 and 1 should be clustered together
        assert len(result) == 2
        assert len(result[0]) == 2  # Two groups clustered together
        assert len(result[1]) == 1  # One group alone

    @patch("newvelles.models.grouping.process_content")
    @patch("newvelles.models.grouping.TfidfVectorizer")
    @patch("newvelles.models.grouping.cosine_similarity")
    def test_cluster_groups_no_clustering(
        self, mock_cosine, mock_vectorizer, mock_process
    ):
        """Test when groups are not similar enough to cluster."""
        mock_process.side_effect = lambda x: x.lower().split()

        mock_tfidf = Mock()
        mock_vectorizer.return_value = mock_tfidf
        mock_tfidf.fit_transform.return_value = "mocked_matrix"

        # All groups have low similarity
        similarity_matrix = np.array(
            [[1.0, 0.2, 0.1], [0.2, 1.0, 0.3], [0.1, 0.3, 1.0]]
        )
        mock_cosine.return_value = similarity_matrix

        groups = [[0, 1], [2, 3], [4, 5]]
        titles = [
            "Apple iPhone",
            "Apple iPad",
            "Tesla car",
            "Tesla truck",
            "Biden policy",
            "Biden speech",
        ]

        result = cluster_groups(groups, titles, context_similarity_threshold=0.5)

        # No clustering should occur
        assert len(result) == 3
        for cluster in result:
            assert len(cluster) == 1


class TestExtractCommonSubstrings:
    """Test extract_common_substrings function."""

    def test_extract_common_substrings_basic(self):
        """Test basic functionality of extract_common_substrings."""
        titles = [
            "Apple announces new iPhone model",
            "Apple reveals iPhone specifications",
            "Apple iPhone pricing details",
        ]

        result = extract_common_substrings(titles)

        # Should find common substrings
        assert "Apple" in result
        assert "iPhone" in result

        # Should be sorted by length (longest first)
        assert len(result[0]) >= len(result[-1])

    def test_extract_common_substrings_min_length(self):
        """Test extract_common_substrings with custom min_length."""
        titles = ["AI technology advances", "AI research breakthrough"]

        result = extract_common_substrings(titles, min_length=5)

        # Should only include substrings >= 5 characters
        for substring in result:
            assert len(substring) >= 5

    def test_extract_common_substrings_no_common(self):
        """Test when there are no common substrings."""
        titles = ["Apple", "Tesla", "Microsoft"]

        result = extract_common_substrings(titles, min_length=3)

        # Should return empty list
        assert len(result) == 0

    def test_extract_common_substrings_single_title(self):
        """Test with single title."""
        titles = ["Single title"]

        result = extract_common_substrings(titles)

        # Should return empty list
        assert len(result) == 0


class TestIdentifyGroup:
    """Test identify_group function."""

    @patch("newvelles.models.grouping.extract_common_substrings")
    def test_identify_group_basic(self, mock_extract):
        """Test basic functionality of identify_group."""
        mock_extract.return_value = ["Apple iPhone", "Apple", "iPhone", "new"]

        titles = ["Apple iPhone news", "Apple iPhone release"]

        result = identify_group(titles)

        # Should use top 3 common substrings
        expected = "Apple iPhone Apple iPhone"
        assert result == expected

    @patch("newvelles.models.grouping.extract_common_substrings")
    def test_identify_group_fewer_than_three(self, mock_extract):
        """Test when fewer than 3 common substrings are found."""
        mock_extract.return_value = ["Apple", "iPhone"]

        titles = ["Apple iPhone news", "Apple iPhone release"]

        result = identify_group(titles)

        # Should use all available substrings
        expected = "Apple iPhone"
        assert result == expected

    @patch("newvelles.models.grouping.extract_common_substrings")
    def test_identify_group_no_common(self, mock_extract):
        """Test when no common substrings are found."""
        mock_extract.return_value = []

        titles = ["Different", "Completely different"]

        result = identify_group(titles)

        # Should return empty string
        assert result == ""


class TestBuildNewsGroups:
    """Test build_news_groups function."""

    @patch("newvelles.models.grouping.group_similar_titles")
    @patch("newvelles.models.grouping.cluster_groups")
    @patch("newvelles.models.grouping.identify_group")
    def test_build_news_groups_basic(self, mock_identify, mock_cluster, mock_group):
        """Test basic functionality of build_news_groups."""
        # Mock the pipeline
        mock_group.return_value = [[0, 1], [2, 3]]
        mock_cluster.return_value = [[[0, 1]], [[2, 3]]]
        mock_identify.side_effect = [
            "Tech News",
            "Tech iPhone",
            "Business News",
            "Business Earnings",
        ]

        titles = ["iPhone release", "iPhone specs", "Tesla earnings", "Tesla stock"]

        result = build_news_groups(titles)

        # Should return nested dictionary structure
        assert isinstance(result, dict)
        assert "Tech News" in result
        assert "Business News" in result

        # Each top-level group should have sub-groups
        assert "Tech iPhone" in result["Tech News"]
        assert "Business Earnings" in result["Business News"]


class TestBuildVisualization:
    """Test build_visualization function."""

    @patch("newvelles.models.grouping.build_news_groups")
    def test_build_visualization_basic(self, mock_build_groups):
        """Test basic functionality of build_visualization."""
        # Mock news groups
        mock_build_groups.return_value = {
            "Tech News": {"iPhone News": ["iPhone 15 released", "iPhone 15 specs"]}
        }

        # Create mock title_data
        title_data = {
            "iPhone 15 released": NewsEntry(
                title="iPhone 15 released",
                link="https://example.com/iphone",
                published="2025-01-16",
                title_detail_base="example.com",
            ),
            "iPhone 15 specs": NewsEntry(
                title="iPhone 15 specs",
                link="https://example.com/specs",
                published="2025-01-16",
                title_detail_base="example.com",
            ),
        }

        result, title_groups = build_visualization(title_data)

        # Should return visualization dictionary and empty title_groups
        assert isinstance(result, dict)
        assert isinstance(title_groups, dict)
        assert len(title_groups) == 0

        # Should have correct structure
        assert "Tech News" in result
        assert "iPhone News" in result["Tech News"]

    def test_build_visualization_list_format(self):
        """Test build_visualization with list format entries."""
        title_data = {
            "Test Article": [
                "Test Article",
                "https://example.com",
                "example.com",
                "2025-01-16",
            ]
        }

        with patch("newvelles.models.grouping.build_news_groups") as mock_build_groups:
            mock_build_groups.return_value = {
                "Test Group": {"Test Subgroup": ["Test Article"]}
            }

            result, _ = build_visualization(title_data)

            # Should handle list format correctly
            assert "Test Group" in result
            assert "Test Subgroup" in result["Test Group"]
            assert "Test Article" in result["Test Group"]["Test Subgroup"]

    @patch("newvelles.models.grouping.build_visualization")
    def test_build_visualization_lite(self, mock_build_viz):
        """Test build_visualization_lite function."""
        mock_build_viz.return_value = ({}, {})

        title_data = {"Test": NewsEntry("Test", "url", "date", "base")}

        result = build_visualization_lite(title_data, cluster_limit=5)

        # Should call build_visualization with same parameters
        mock_build_viz.assert_called_once_with(title_data, 5)


class TestConstants:
    """Test module constants."""

    def test_visualization_version(self):
        """Test that VISUALIZATION_VERSION is defined."""
        assert isinstance(VISUALIZATION_VERSION, str)
        assert len(VISUALIZATION_VERSION) > 0
