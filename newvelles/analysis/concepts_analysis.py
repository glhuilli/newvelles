from collections import defaultdict
import json
import os
import pickle
import uuid
from typing import Dict, Iterable, NamedTuple, List

import click
from newvelles.analysis.json_schema import JSON_SCHEMA
from newvelles.analysis.exclude_concepts import EXCLUDE_CONCEPTS
from newvelles.utils.openai import ask_chatgpt_with_retries, OPEN_AI_TOKEN_LIMIT
import spacy
from tqdm import tqdm


nlp = spacy.load("en_core_web_sm")
OPEN_AI_TOKEN_LIMIT_BUFFER = 2000  # for prompt context
PROMPT_LIMIT = OPEN_AI_TOKEN_LIMIT - OPEN_AI_TOKEN_LIMIT_BUFFER


class WeightedConcept(NamedTuple):
    concept: str
    weight: float
    categories: List[str]


class ChatGPTConcepts(NamedTuple):
    terms: List[str]
    categories: List[str]


class TitleSummary(NamedTuple):
    title: str
    raw_concept: Dict[str, int]


def load_data(filename):
    """
    Load data from a pickle file
    """
    with open(filename, 'rb') as f:
        return pickle.load(f)


def get_concepts(content: str) -> List[ChatGPTConcepts]:
    """
    Retrieves data from ChatGPT response.

    The expectation is that the content variable is following the json schema specified in the prompt.
    """
    concepts = json.loads(content).get('concepts')
    output = []
    for concept in concepts:
        terms = concept.get('terms')
        categories = concept.get('categories')
        if terms and categories:
            output.append(ChatGPTConcepts(terms=terms, categories=categories))
    return output


def summarize_titles(titles: List[str], limit=3000) -> (List[TitleSummary], Dict[str, int]):
    """
    Summarizes titles given that ChatGPT can only process 4098 tokens

    Use SpaCy to extract main concepts, then
        1. Make sure to keep the longest concepts
        2.
    """
    title_summaries = []
    raw_concepts_freq = defaultdict(int)
    for title in tqdm(titles, 'Processing titles'):
        # Process the text with spaCy
        doc = nlp(title)
        named_entities = [ent.text for ent in doc.ents if ent.text not in EXCLUDE_CONCEPTS]
        noun_chunks = [chunk.text for chunk in doc.noun_chunks if chunk.text not in EXCLUDE_CONCEPTS]
        tokens = [token.lemma_.lower() for token in doc if not token.is_stop and token.is_alpha if token.lemma_.lower() not in EXCLUDE_CONCEPTS]
        terms = list(set(x.lower() for x in named_entities + noun_chunks + tokens))
        for term in terms:
            raw_concepts_freq[term] += 1
        title_summaries.append(_generate_summary_title(terms))
    return _enforce_openai_limits(title_summaries, limit), raw_concepts_freq


def _generate_summary_title(terms: List[str]) -> str:
    """
    Keep longest terms that include other terms in the summarized title.

    Note that inclusion in this case is a simple full string matching, not based on regex.
    """
    # Sort list by length of items in descending order
    terms.sort(key=lambda s: len(s.split()), reverse=True)

    is_included = [False] * len(terms)
    for i in range(len(terms)):
        for j in range(i + 1, len(terms)):
            if set(terms[j].split()).issubset(set(terms[i].split())):
                is_included[j] = True

    # Use all that are not marked as included
    return ' '.join(term for term, included in zip(terms, is_included) if not included)


def _enforce_openai_limits(titles: List[str], limit: int = 40000) -> List[str]:
    """
    Only keep the summaries that provide most information using limit as the upper bound to how many

    Most information means
    1. Has the most words post NLP processing

    TODO: improve the notion of "most information".
    """
    final_titles = []
    total = 0
    titles.sort(key=lambda s: len(s.split()), reverse=True)
    for t in titles:
        if total > limit:
            break
        final_titles.append(t)
        total += len(t.split())
    return final_titles


def get_concepts_and_weights(
        chatgpt_data: Iterable[ChatGPTConcepts], raw_concepts: Dict[str, int]) -> List[WeightedConcept]:
    """
    Check all concepts from ChatGPT and add their weights and categories
    """
    total_freq = sum(list(raw_concepts.values()))
    concept_weights = defaultdict(float)
    concept_categories = defaultdict(list)
    concepts = {}
    for chatgpt_concepts in chatgpt_data:
        preprocessed_concepts = list(set(chatgpt_concepts.terms))
        categories = chatgpt_concepts.categories
        for term in preprocessed_concepts:
            if term in concepts:
                # means that we already processed this concept, should be skipped.
                continue
            raw_concept_freq = raw_concepts.get(term, 0)
            if raw_concept_freq == 0:
                print(f'had raw_concept frequency 0 : {term}')
            raw_concept_weight = raw_concept_freq/total_freq
            concept_weights[term] = raw_concept_weight
            concept_categories[term].append(categories)
            concepts[term] = None
    for concept, categories_list in concept_categories.items():
        unique_categories = []
        for categories in categories_list:
            for c in categories:
                if c not in unique_categories:
                    unique_categories.append(c)
        concepts[concept] = WeightedConcept(
            concept=concept, categories=unique_categories, weight=concept_weights.get(concept))
    return list(concepts.values())


def _split_titles(titles: List[str], max_title_words: int = 30):
    groups = []
    current_group = []
    current_word_count = 0

    for title in titles:
        title_word_count = len(title.split())

        if current_word_count + title_word_count <= max_title_words:
            # Add the title to the current group and update the word count
            current_group.append(title)
            current_word_count += title_word_count
        else:
            # Add the current group to the list of groups
            groups.append(current_group)
            # Start a new group with the current title and update the word count
            current_group = [title]
            current_word_count = title_word_count

    # Add the last group to the list of groups
    if current_group:
        groups.append(current_group)

    return groups


def _join_raw_concepts(raw_concepts_list: List[Dict[str, int]]) -> Dict[str, int]:
    final = defaultdict(int)
    for raw_concepts in raw_concepts_list:
        for concept, frequency in raw_concepts.items():
            final[concept] = final.get(concept, 0) + frequency
    return final


def load_all_pickles(directory):
    # Create an empty list to store the contents of the pickle files
    data = []

    # Loop over all files in the directory
    for filename in os.listdir(directory):
        # Check if the file is a pickle file
        if filename.endswith(".pkl"):
            # Construct the full file path
            file_path = os.path.join(directory, filename)

            # Open the pickle file and add its contents to the list
            with open(file_path, 'rb') as f:
                data.append(pickle.load(f))

    return data


def _load_processed_titles(directory):
    titles = {}
    all_data = load_all_pickles(directory)
    for data in all_data:
        if data.get('processed_titles') and type(data.get('processed_titles')) == dict:
            if data.get('processed_titles').get('title_chunk'):
                for title in data.get('processed_titles').get('title_chunk'):
                    titles[title] = 1
    return titles


def _load_raw_concepts(directory):
    raw_concepts_list = []
    all_data = load_all_pickles(directory)
    for data in all_data:
        if data.get('processed_titles') and type(data.get('processed_titles')) == dict:
            if data.get('processed_titles').get('raw_concepts'):
                raw_concepts_list.append(data.get('processed_titles').get('raw_concepts'))
    return raw_concepts_list


def get_concepts_openai(titles: List[str], max_title_words: int = 100):
    """
    Get concepts by calling ChatGPT. Big constraint is that we can't send more than 4096 tokens, so we need
    to summarize all the titles.

    To do this, we'll use some old school NLP:
    1. Extract named entities from titles
    2. Extract noun chunks
    3. Extract tokens that are not stop words or alpha numeric
    4. Generate a list of the top N tokens
    """
    print(f'original titles: {len(titles)}')
    titles = list(set([x.lower().strip() for x in titles]))  # dedup titles
    print(f'dedup titles: {len(titles)}')

    raw_concepts_list = []
    final_chatgpt_data = []

    titles_cache = _load_processed_titles('./data/analysis/chatgpt_data/')
    titles_to_process = [t for t in titles if t not in titles_cache ]
    print(f'titles to process: {len(titles_to_process)}')

    for k, title_chunk in enumerate(
            tqdm(_split_titles(titles_to_process, max_title_words=max_title_words), 'Processing title groups')):

        # TODO: check if title chunk was already processed in pickle files and skip

        prompt_format = f'\n\n Extract terms and potential categories and ' \
            f'only provide a RFC8259 compliant JSON using this json schema: {JSON_SCHEMA}'

        summaries, raw_concepts = summarize_titles(title_chunk, limit=PROMPT_LIMIT)
        raw_concepts_list.append(raw_concepts)

        analysis_string = '\n'.join(summaries)
        prompt = f'Process the following summarized titles:\n{analysis_string}'
        chatgpt_data = ask_chatgpt_with_retries(prompt, prompt_format, get_concepts, retries=3)
        if chatgpt_data.get('parsed_response'):
            with open(f'./data/analysis/chatgpt_data/title_chunk_{str(uuid.uuid4())}.pkl', 'wb') as f:
                chatgpt_data['processed_titles'] = {'title_chunk': title_chunk,
                                                    'summaries': summaries,
                                                    'raw_concepts': raw_concepts,
                                                    'analysis_string': analysis_string}
                pickle.dump(chatgpt_data, f)
            final_chatgpt_data += chatgpt_data.get('parsed_response')

    final_raw_concepts = _join_raw_concepts(raw_concepts_list)
    print(final_raw_concepts)
    return get_concepts_and_weights(final_chatgpt_data, final_raw_concepts)


@click.command()
@click.option('--input_data', default='./data/analysis/newvelles-data-bucket.pkl', help='Input file')
@click.option('--output_data', default='./data/analysis/newvelles-data-concepts.pkl', help='Output file')
@click.option('--max_title_words', default=100,
              help='words that will be included in the group of titles to call ChatGPT')
def main(input_data, output_data, max_title_words):
    # load the max title words
    max_title_words = int(max_title_words)
    # Load grouped data
    grouped_data = load_data(input_data)
    # Initialize an empty dictionary to store the analysis results
    analysis_results = {}

    # Analyze data
    for year, year_data in grouped_data.items():
        print(f'processing year: {year}')
        for month, month_data in year_data.items():
            print(f'month {month}')
            for week_start, titles in tqdm(month_data.items(), 'processing monthly data'):
                concepts = get_concepts_openai(titles, max_title_words=max_title_words)
                if year not in analysis_results:
                    analysis_results[year] = {}
                if month not in analysis_results[year]:
                    analysis_results[year][month] = {}
                analysis_results[year][month][week_start] = concepts

    # Save the analysis results
    with open(output_data, 'wb') as f:
        pickle.dump(analysis_results, f)


if __name__ == '__main__':
    main()
