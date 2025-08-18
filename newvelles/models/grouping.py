import json
from collections import defaultdict
from typing import Dict, List, Tuple

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from newvelles.config import debug
from newvelles.feed import NewsEntry
from newvelles.utils.text import process_content

# This version needs to be updated in case major
# changes are done to the visualization files below.
VISUALIZATION_VERSION = "0.2.1"
DEBUG = debug()

# if os.environ.get('AWS_LAMBDA'):
#     _EMBEDDING_SP, _EMBEDDING_MODULE = load_embedding_model_lite()
# else:
#     _EMBEDDING_MODEL = load_embedding_model()


"""
1. Use a similarity measure to group similar titles
    1.1. Cosine similarity with TF-IDF (TODO: try embeddings)
    1.2. Preprocess the titles (remove stop words, numbers, etc.)
3. Cluster the groups into top-level groups based on context similarity
4. Extract common substrings for lower-level and top-level groups
5. Filter out groups with fewer than 2 titles
"""


def group_similar_titles(titles: List[str], similarity_threshold: float = 0.7) -> List[List[int]]:
    # Group similar titles using TF-IDF and cosine similarity
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

        if len(group) >= 2:  # Groups with less than 2 titles are not interesting
            groups.append(group)

    return groups


def cluster_groups(
    groups: List[List[int]],
    titles: List[str],
    context_similarity_threshold: float = 0.5,
) -> List[List[List[int]]]:
    # Cluster groups into top-level groups based on context similarity
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


def extract_common_substrings(titles: List[str], min_length: int = 3) -> List[str]:
    # Extract common substrings from a list of titles
    def find_common_substrings(s1: str, s2: str) -> List[str]:
        common = []
        for i in range(len(s1)):
            for j in range(i + min_length, len(s1) + 1):
                substring = s1[i:j]
                if (
                    substring in s2 and len(substring) >= min_length
                ):  # Substrings must be at least min_length characters
                    common.append(substring)
        return common

    common_substrings = set()
    for i, title_i in enumerate(titles):
        for j in range(i + 1, len(titles)):
            common_substrings.update(find_common_substrings(title_i, titles[j]))

    return sorted(list(common_substrings), key=len, reverse=True)


def identify_group(titles: List[str]) -> str:
    # Identify a group by the most common substrings
    common_substrings = extract_common_substrings(titles)
    return " ".join(common_substrings[:3])  # Use top 3 common substrings


def build_news_groups(titles: List[str]) -> Dict[str, Dict[str, List[str]]]:
    # Main function to build the news groups
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
    result_dict = dict(visualization)
    for k1, v1 in result_dict.items():
        result_dict[k1] = dict(v1)
        for k2, v2 in result_dict[k1].items():
            result_dict[k1][k2] = dict(v2)
            for k3, v3 in result_dict[k1][k2].items():
                if isinstance(v3, defaultdict):
                    result_dict[k1][k2][k3] = dict(v3)

    return (
        result_dict,
        {},
    )  # Return an empty dict for title_groups as it's no longer used


# def generate_top_words(groups_indexes, similar_sets, sentences):
#     top_words_group = defaultdict(list)
#     all_sentences = set()
#     for idx, group_indexes in groups_indexes.items():
#         grp_sentences = set()
#         if len(group_indexes) > 1:
#             for gidx in group_indexes:
#                 for ss in similar_sets:
#                     if ss[0] == gidx:
#                         for gidx2 in group_indexes:
#                             if gidx2 in ss[1] and gidx != gidx2:
#                                 grp_sentences.add(sentences[gidx])
#                                 all_sentences.add(sentences[gidx])
#         if DEBUG:
#             print(get_top_words_spacy(list(grp_sentences)))
#         top_words_group[idx] = ' '.join([x[0] for x in get_top_words_spacy(list(grp_sentences))])
#     if DEBUG:
#         print(f'Total news articles: {len(all_sentences)}')
#         print(get_top_words_spacy(list(all_sentences), top_n=50))

#     return top_words_group


def build_visualization_lite(
    title_data: Dict[str, NewsEntry], cluster_limit: int = 0
) -> Tuple[Dict[str, Dict[str, Dict[str, Dict[str, str]]]], Dict[int, List[str]]]:
    """
    data is defined by {sentence: link}
    """
    return build_visualization(title_data, cluster_limit)


# def build_visualization_old(
#         title_data: Dict[str, NewsEntry],
#         cluster_limit: int = 0) -> Tuple[Dict[int, Dict[str, List[str]]], Dict[int, List[str]]]:
#     """
#     data is defined by {sentence: link}

#     TODO: refactor this method so it's easier to understand.
#     TODO: Use the limit to generate only top N news
#     """
#     titles = [x[0] for x in title_data.items() if x[0]]

#     # Depending on whether we are on AWS Lambda or not, we use different clustering algorithm
#     if os.environ.get('AWS_LAMBDA'):
#         similar_sets, unique_sets = group_sentences_lite(_EMBEDDING_SP, _EMBEDDING_MODULE, titles)
#     else:
#         similar_sets, unique_sets = group_sentences(_EMBEDDING_MODEL, titles)

#     # TODO: consider removing title_groups (currently only used for debugging)
#     title_groups = defaultdict(list)
#     title_groups_indexes = defaultdict(list)
#     for idx, group in enumerate(
#             sorted([x for x in unique_sets if len(x) > cluster_limit - 1],
#                    key=lambda x: len(x),
#                    reverse=True)):
#         for title_idx in group:
#             title_groups[idx].append(titles[title_idx])
#             title_groups_indexes[idx].append(title_idx)

#     top_words_group = generate_top_words(title_groups_indexes, similar_sets, titles)
#     visualization = defaultdict(
#         lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(str)))
#     )
#     for idx, group_indexes in title_groups_indexes.items():
#         grp_top_words = top_words_group[idx]
#         if len(group_indexes) > cluster_limit:
#             if len(group_indexes) == 2:  # Needed to remove duplicate groups
#                 grp_idx = group_indexes[0]
#                 grp_idx_header, group_titles = get_top_words_gidx(grp_idx, group_indexes,
#                                                                   similar_sets, titles)
#                 for title in group_titles:
#                     visualization[grp_top_words][grp_idx_header][title] = dict(
#                         title_data[title]._asdict())
#             else:
#                 for grp_idx in group_indexes:
#                     grp_idx_header, group_titles = get_top_words_gidx(grp_idx, group_indexes,
#                                                                       similar_sets, titles)
#                     for title in group_titles:
#                         visualization[grp_top_words][grp_idx_header][title] = dict(
#                             title_data[title]._asdict())

#         # TODO: review if should include "other" news or not
#         #  not convinced yet it helps as it's too much noise.
#         # if include_other:
#         #     grp_idx = group_indexes[0]
#         #     visualization['other']['news'][titles[grp_idx]] = title_link[
#         #         titles[grp_idx]]
#     if DEBUG:
#         print(json.dumps(visualization, indent=2))
#     return visualization, title_groups


# def get_top_words_gidx(grp_idx, group_indexes, similar_sets, titles):
#     added = {grp_idx}
#     group_titles = [titles[grp_idx]]
#     for ss in similar_sets:
#         if ss[0] == grp_idx:
#             for grp_idx2 in group_indexes:
#                 if grp_idx2 in added:
#                     continue
#                 if grp_idx2 in ss[1] and grp_idx != grp_idx2:
#                     group_titles.append(titles[grp_idx2])
#                     added.add(grp_idx2)
#     grp_idx_header = ' '.join([x[0] for x in get_top_words_spacy(group_titles, top_n=5)])
#     return grp_idx_header, group_titles
