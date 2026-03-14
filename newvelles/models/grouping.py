import json
import re
from collections import defaultdict
from typing import Dict, List, Tuple

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from newvelles.config import debug
from newvelles.feed import NewsEntry
from newvelles.utils.text import process_content, remove_stopwords, get_sentence_score

# This version needs to be updated in case major
# changes are done to the visualization files below.
VISUALIZATION_VERSION = "0.2.1"
DEBUG = debug()

# Algorithm constants
DEFAULT_SIMILARITY_THRESHOLD = 0.25
DEFAULT_CONTEXT_SIMILARITY_THRESHOLD = 0.2
MIN_SUBSTRING_LENGTH = 3
MAX_SUBSTRING_WORDS = 5
TOP_SUBSTRINGS_LIMIT = 3
OVERLAP_FILTER_THRESHOLD = 0.5
MIN_GROUP_SIZE = 2

"""
1. Use a similarity measure to group similar titles
    1.1. Cosine similarity with TF-IDF (TODO: try embeddings)
    1.2. Preprocess the titles (remove stop words, numbers, etc.)
3. Cluster the groups into top-level groups based on context similarity
4. Extract common substrings for lower-level and top-level groups
5. Filter out groups with fewer than 2 titles
"""


def group_similar_titles(titles: List[str], similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD) -> List[List[int]]:
    """
    Group similar titles using TF-IDF and cosine similarity.

    Args:
        titles: List of news article titles to group
        similarity_threshold: Minimum cosine similarity to consider titles as similar

    Returns:
        List of groups, where each group is a list of title indices
    """
    preprocessed_titles = [" ".join(process_content(title)) for title in titles]
    vectorizer = TfidfVectorizer()
    tfidf_matrix = vectorizer.fit_transform(preprocessed_titles)
    similarity_matrix = cosine_similarity(tfidf_matrix)

    groups = []
    used_indices = set()  # Used to avoid duplicate groups

    for i in range(len(titles)):
        if i in used_indices:
            continue

        group = [i]
        used_indices.add(i)

        for j in range(i + 1, len(titles)):
            if j in used_indices:
                continue

            if similarity_matrix[i, j] >= similarity_threshold:
                group.append(j)
                used_indices.add(j)

        if len(group) >= MIN_GROUP_SIZE:
            groups.append(group)

    return groups


def cluster_groups(
    groups: List[List[int]],
    titles: List[str],
    context_similarity_threshold: float = DEFAULT_CONTEXT_SIMILARITY_THRESHOLD,
) -> List[List[List[int]]]:
    """
    Cluster groups into top-level groups based on context similarity.

    Takes existing groups of similar titles and further clusters them into
    higher-level groups based on contextual similarity.

    Args:
        groups: List of groups (each group is a list of title indices)
        titles: Original list of titles
        context_similarity_threshold: Minimum similarity to cluster groups together

    Returns:
        List of clustered groups, where each cluster contains multiple groups
    """
    group_representations = []
    for group in groups:
        group_text = " ".join([titles[i] for i in group])  # Join group titles
        group_representations.append(" ".join(process_content(group_text)))  # Preprocess and join

    vectorizer = TfidfVectorizer()
    tfidf_matrix = vectorizer.fit_transform(group_representations)
    similarity_matrix = cosine_similarity(tfidf_matrix)

    top_level_groups = []
    used_groups = set()

    for i, group_i in enumerate(groups):
        if i in used_groups:  # Avoid duplicate groups
            continue

        top_level_group = [group_i]
        used_groups.add(i)

        for j in range(i + 1, len(groups)):
            if j in used_groups:
                continue

            if similarity_matrix[i, j] >= context_similarity_threshold:
                top_level_group.append(groups[j])
                used_groups.add(j)

        top_level_groups.append(top_level_group)

    return top_level_groups


def _is_word_boundary(text: str, pos: int) -> bool:
    """Check if position is at a word boundary (start/end or adjacent to space/punctuation)."""
    if pos == 0 or pos == len(text):
        return True
    # Check if character at position-1 or position is whitespace or punctuation
    if pos > 0 and re.match(r'[\s\W]', text[pos - 1]):
        return True
    if pos < len(text) and re.match(r'[\s\W]', text[pos]):
        return True
    return False


def extract_common_substrings(titles: List[str], min_length: int = MIN_SUBSTRING_LENGTH) -> List[str]:
    """
    Extract common substrings from titles, respecting word boundaries.
    Only returns substrings that start and end at word boundaries to avoid fragments.
    """
    def find_common_substrings(s1: str, s2: str) -> List[str]:
        original_s1 = str(s1)
        s1 = s1.strip().lower()
        s2 = s2.strip().lower()
        common = []
        for i in range(len(s1)):
            # Only start at word boundaries
            if not _is_word_boundary(s1, i):
                continue

            for j in range(i + min_length, len(s1) + 1):
                # Only end at word boundaries
                if not _is_word_boundary(s1, j):
                    continue

                substring = s1[i:j]
                if len(substring) >= min_length and substring in s2:
                    # Verify this substring also appears at word boundary in s2
                    s2_pos = s2.find(substring)
                    if s2_pos != -1 and _is_word_boundary(s2, s2_pos) and _is_word_boundary(s2, s2_pos + len(substring)):
                        common.append(original_s1[i:j].strip())
        return common

    common_substrings = set()
    for i, title_i in enumerate(titles):
        for j in range(i + 1, len(titles)):
            common_substrings.update(find_common_substrings(title_i, titles[j]))

    # Filter out empty strings
    common_substrings = {s for s in common_substrings if s}

    return sorted(list(common_substrings), key=len, reverse=True)


def _filter_highly_overlapping_phrases(phrases: List[str], overlap_threshold: float = OVERLAP_FILTER_THRESHOLD) -> List[str]:
    """
    Keep only phrases that are not highly overlapping with any longer phrase selected so far.

    For each phrase (sorted from longest to shortest), if its word overlap ratio with any selected
    phrase is above the threshold (i.e. is mostly contained), skip it; else, keep it.

    Uses case-insensitive comparison to avoid treating "Oil Prices" and "oil prices" as different.

    Args:
        phrases: List of phrases to filter
        overlap_threshold: Threshold for considering phrases overlapping (default 0.5)

    Returns:
        List of non-overlapping phrases
    """
    selected = []
    # Ensure phrases are sorted from longest to shortest before processing
    phrases = sorted(phrases, key=lambda s: len(s.split()), reverse=True)
    # Create lowercase word sets for case-insensitive comparison
    phrase_words_lower = [set(w.lower() for w in p.split()) for p in phrases]

    for i, phrase in enumerate(phrases):
        words_lower = phrase_words_lower[i]
        skip = False
        for j, selected_phrase in enumerate(selected):
            # Use lowercase word set for selected phrase
            selected_words_lower = set(w.lower() for w in selected_phrase.split())
            if not words_lower or not selected_words_lower:
                continue
            # Calculate overlap using case-insensitive word sets
            overlap = len(words_lower & selected_words_lower) / max(len(words_lower), 1)
            # If > overlap_threshold, phrase is mostly contained in selected_phrase
            if overlap >= overlap_threshold:
                skip = True
                break
        if not skip:
            selected.append(phrase)

    return selected


def identify_group(titles: List[str]) -> str:
    """
    Generate a unique identifier for a group of titles using common substrings.

    Algorithm:
    1. Normalizes titles (removes punctuation, stop words)
    2. Extracts common substrings that respect word boundaries
    3. Ranks substrings by importance using sentence scores
    4. Filters overlapping phrases (>50% word overlap)
    5. Returns top 3 substrings wrapped in brackets

    Args:
        titles: List of titles to identify

    Returns:
        Group identifier string in format "[phrase1] [phrase2] [phrase3]"
        or empty string if no common substrings found
    """
    # Normalize titles: remove all non-alphanumeric characters except "&" and "-", collapse extra spaces
    normalized_titles = []
    for title in titles:
        # Remove all characters except alphanumerics, whitespace, "&", and "-"
        title_clean = re.sub(r"[^\w\s&\-]", "", title)
        # Collapse multiple spaces to one
        title_clean = re.sub(r"\s+", " ", title_clean)
        # Strip leading/trailing whitespace
        title_clean = title_clean.strip()

        # Remove stop words
        title_clean = remove_stopwords(title_clean.split())
        title_clean = ' '.join(title_clean)

        normalized_titles.append(title_clean)
    titles = normalized_titles

    if len(titles) < MIN_GROUP_SIZE:
        return ""

    # Get common substrings (sorted by character length, longest first)
    common_substrings = [x for x in extract_common_substrings(titles) if len(x.split(' ')) < MAX_SUBSTRING_WORDS]

    if not common_substrings:
        return ""

    filtered_sorted = sorted(common_substrings, key=get_sentence_score, reverse=True)

    # Filter out overlapped phrases
    filtered_sorted = _filter_highly_overlapping_phrases(filtered_sorted, overlap_threshold=OVERLAP_FILTER_THRESHOLD)

    # Take top N non-overlapping substrings
    top_substrings = filtered_sorted[:TOP_SUBSTRINGS_LIMIT]
    if not top_substrings:
        return ""

    # Enclose each top substring in brackets, e.g. "x" -> "[x]"
    top_substrings = [f"[{s}]" for s in top_substrings]

    # Join and clean
    result = " ".join(top_substrings)

    return result


def rank_news_groups(groups: Dict) -> Dict:
    """
    Rank/sort news groups according to priority rules.

    Ranking rules (in priority order):
    1. Multi-phrase groups (2+ top-level phrases) rank higher than single-phrase groups
    2. For single-phrase groups: multi-word phrases rank higher than single-word phrases
    3. Within each category, more sub-groupings rank higher
    4. Within each category, more total news items rank higher
    5. Single-phrase groups with 1 word, 1 sub-group, and 2 news go to the very bottom

    Args:
        groups: Dictionary of news groups (top-level -> sub-groups -> articles)

    Returns:
        Dictionary of groups sorted by ranking priority (dict maintains insertion order in Python 3.7+)
    """
    def get_ranking_key(item):
        top_group_id, sub_groups = item

        # Count top-level phrases (phrases between brackets)
        phrase_count = len([p.strip()
                           for p in top_group_id.replace('[', '|').replace(']', '').split('|')
                           if p.strip()])

        # Count sub-groupings
        sub_group_count = len(sub_groups)

        # Count total news items across all sub-groups
        total_news = sum(len(articles) for articles in sub_groups.values())

        # Multi-phrase groups rank higher (use negative to sort descending)
        # is_multi_phrase = 1 for multi-phrase, 0 for single-phrase
        # We negate to put 1 (multi-phrase) first
        is_multi_phrase = 1 if phrase_count > 1 else 0

        # For single-phrase groups, count words in the phrase
        # Multi-word phrases should rank higher than single-word phrases
        if phrase_count == 1:
            word_count = len(top_group_id.replace('[', '').replace(']', '').strip().split())
        else:
            # For multi-phrase groups, word count doesn't matter (use large value)
            word_count = 999

        return (
            -is_multi_phrase,     # Multi-phrase first (negative for descending)
            -word_count,          # More words first (negative for descending)
            -sub_group_count,     # More sub-groups first (negative for descending)
            -total_news           # More news first (negative for descending)
        )

    # Sort groups by ranking key
    sorted_items = sorted(groups.items(), key=get_ranking_key)

    # Return as dict (Python 3.7+ maintains insertion order)
    return dict(sorted_items)


def build_news_groups(titles: List[str]) -> Dict[str, Dict[str, List[str]]]:
    """
    Build hierarchical news groups from titles.

    Main pipeline that groups similar titles, clusters them into top-level groups,
    and generates identifiers for each level.

    Args:
        titles: List of news article titles

    Returns:
        Nested dictionary mapping top-level identifiers to sub-groups to titles
    """
    groups = group_similar_titles(titles)
    top_level_groups = cluster_groups(groups, titles)

    result: Dict[str, Dict[str, List[str]]] = {}
    for top_group in top_level_groups:
        top_level_titles = [titles[i] for group in top_group for i in group]
        top_level_identifier = identify_group(top_level_titles)

        result[top_level_identifier] = {}
        for group in top_group:
            group_titles = [titles[i] for i in group]
            group_identifier = identify_group(group_titles)
            result[top_level_identifier][group_identifier] = group_titles

    return result


def build_visualization(
    title_data: Dict[str, NewsEntry], cluster_limit: int = 0  # pylint: disable=unused-argument
) -> Tuple[Dict[str, Dict[str, Dict[str, Dict[str, str]]]], Dict[int, List[str]]]:
    """
    data is defined by {sentence: link}

    TODO: refactor this method so it's easier to understand.
    TODO: Use the limit to generate only top N news
    """
    titles = [x[0] for x in title_data.items() if x[0]]

    # Use the news grouping algorithm
    news_groups = build_news_groups(titles)
    
    visualization: defaultdict = defaultdict(
        lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(str)))
    )
    for top_level_group, lower_level_groups in news_groups.items():
        for lower_level_group, group_titles in lower_level_groups.items():
            for title in group_titles:
                entry = title_data[title]
                # Handle both NewsEntry and list cases
                if hasattr(entry, "_asdict"):
                    entry_dict = entry._asdict()
                    # Transform field names for consistency with output format
                    if "published" in entry_dict:
                        entry_dict["timestamp"] = entry_dict.pop("published")
                    if "title_detail_base" in entry_dict:
                        entry_dict["source"] = entry_dict.pop("title_detail_base")
                else:
                    # Assuming the list contains the same fields as NewsEntry in order
                    # NewsEntry order: title, link, published, title_detail_base
                    entry_dict = {
                        "title": entry[0] if len(entry) > 0 else "",
                        "link": entry[1] if len(entry) > 1 else "",
                        "timestamp": entry[2] if len(entry) > 2 else "",  # published -> timestamp
                        "source": entry[3] if len(entry) > 3 else "",  # title_detail_base -> source
                    }
                # TODO: build a better top_level_group using get_top_words_spacy
                # and algo similar to generate_top_words
                visualization[top_level_group][lower_level_group][title] = entry_dict

    if DEBUG:
        print(json.dumps(visualization, indent=2))

    # Convert defaultdict to regular dict for proper typing
    result_dict = _convert_defaultdict_to_dict(visualization)

    # Apply ranking to sort groups by priority
    result_dict = rank_news_groups(result_dict)

    # Return an empty dict for title_groups as it's no longer used
    return result_dict, {}


def _convert_defaultdict_to_dict(obj):
    """
    Recursively convert defaultdict to regular dict.

    Args:
        obj: Object to convert (can be defaultdict, dict, or other type)

    Returns:
        Converted object with all defaultdicts replaced by regular dicts
    """
    if isinstance(obj, defaultdict):
        obj = {k: _convert_defaultdict_to_dict(v) for k, v in obj.items()}
    elif isinstance(obj, dict):
        obj = {k: _convert_defaultdict_to_dict(v) for k, v in obj.items()}
    return obj


def build_visualization_lite(
    title_data: Dict[str, NewsEntry], cluster_limit: int = 0
) -> Tuple[Dict[str, Dict[str, Dict[str, Dict[str, str]]]], Dict[int, List[str]]]:
    """
    Lightweight wrapper for build_visualization.

    Args:
        title_data: Dictionary mapping titles to NewsEntry objects
        cluster_limit: Limit on number of clusters (currently unused)

    Returns:
        Tuple of (visualization dict, empty title_groups dict)
    """
    return build_visualization(title_data, cluster_limit)
