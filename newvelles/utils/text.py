import os
import re
from collections import Counter
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np
import tensorflow_hub as hub
from sklearn.metrics.pairwise import cosine_similarity
import sentencepiece as spm
import tensorflow.compat.v1 as tf
tf.disable_v2_behavior()
tf.compat.v1.enable_eager_execution()

_EMBEDDINGS_PATH_LITE = 'https://tfhub.dev/google/universal-sentence-encoder-lite/2'
_EMBEDDINGS_PATH = 'https://tfhub.dev/google/universal-sentence-encoder/3'
_STOPWORDS = frozenset({
    "a", "about", "above", "after", "again", "against", "ain", "all", "am", "an", "and", "any",
    "are", "aren", "aren't", "as", "at", "be", "because", "been", "before", "being", "below",
    "between", "both", "but", "by", "can", "couldn", "couldn't", "d", "did", "didn", "didn't", "do",
    "does", "doesn", "doesn't", "doing", "don", "don't", "down", "during", "each", "few", "for",
    "from", "further", "had", "hadn", "hadn't", "has", "hasn", "hasn't", "have", "haven", "haven't",
    "having", "he", "her", "here", "hers", "herself", "him", "himself", "his", "how", "i", "if",
    "in", "into", "is", "isn", "isn't", "it", "it's", "its", "itself", "just", "ll", "m", "ma",
    "me", "mightn", "mightn't", "more", "most", "mustn", "mustn't", "my", "myself", "needn",
    "needn't", "no", "nor", "not", "now", "o", "of", "off", "on", "once", "only", "or", "other",
    "our", "ours", "ourselves", "out", "over", "own", "re", "s", "same", "shan", "shan't", "she",
    "she's", "should", "should've", "shouldn", "shouldn't", "so", "some", "such", "t", "than",
    "that", "that'll", "the", "their", "theirs", "them", "themselves", "then", "there", "these",
    "they", "this", "those", "through", "to", "too", "under", "until", "up", "ve", "very", "was",
    "wasn", "wasn't", "we", "were", "weren", "weren't", "what", "when", "where", "which", "while",
    "who", "whom", "why", "will", "with", "won", "won't", "wouldn", "wouldn't", "y", "you", "you'd",
    "you'll", "you're", "you've", "your", "yours", "yourself", "yourselves", "could", "he'd",
    "he'll", "he's", "here's", "how's", "i'd", "i'll", "i'm", "i've", "let's", "ought", "she'd",
    "she'll", "that's", "there's", "they'd", "they'll", "they're", "they've", "we'd", "we'll",
    "we're", "we've", "what's", "when's", "where's", "who's", "why's", "would", "able", "abst",
    "accordance", "according", "accordingly", "across", "act", "actually", "added", "adj",
    "affected", "affecting", "affects", "afterwards", "ah", "almost", "alone", "along", "already",
    "also", "although", "always", "among", "amongst", "announce", "another", "anybody", "anyhow",
    "anymore", "anyone", "anything", "anyway", "anyways", "anywhere", "apparently", "approximately",
    "arent", "arise", "around", "aside", "ask", "asking", "auth", "available", "away", "awfully",
    "b", "back", "became", "become", "becomes", "becoming", "beforehand", "begin", "beginning",
    "beginnings", "begins", "behind", "believe", "beside", "besides", "beyond", "biol", "brief",
    "briefly", "c", "ca", "came", "cannot", "can't", "cause", "causes", "certain", "certainly",
    "co", "com", "come", "comes", "contain", "containing", "contains", "couldnt", "date",
    "different", "done", "downwards", "due", "e", "ed", "edu", "effect", "eg", "eight", "eighty",
    "either", "else", "elsewhere", "end", "ending", "enough", "especially", "et", "etc", "even",
    "ever", "every", "everybody", "everyone", "everything", "everywhere", "ex", "except", "f",
    "far", "ff", "fifth", "first", "five", "fix", "followed", "following", "follows", "former",
    "formerly", "forth", "found", "four", "furthermore", "g", "gave", "get", "gets", "getting",
    "give", "given", "gives", "giving", "go", "goes", "gone", "got", "gotten", "h", "happens",
    "hardly", "hed", "hence", "hereafter", "hereby", "herein", "heres", "hereupon", "hes", "hi",
    "hid", "hither", "home", "howbeit", "however", "hundred", "id", "ie", "im", "immediate",
    "immediately", "importance", "important", "inc", "indeed", "index", "information", "instead",
    "invention", "inward", "itd", "it'll", "j", "k", "keep", "keeps", "kept", "kg", "km", "know",
    "known", "knows", "l", "largely", "last", "lately", "later", "latter", "latterly", "least",
    "less", "lest", "let", "lets", "like", "liked", "likely", "line", "little", "'ll", "look",
    "looking", "looks", "ltd", "made", "mainly", "make", "makes", "many", "may", "maybe", "mean",
    "means", "meantime", "meanwhile", "merely", "mg", "might", "million", "miss", "ml", "moreover",
    "mostly", "mr", "mrs", "much", "mug", "must", "n", "na", "name", "namely", "nay", "nd", "near",
    "nearly", "necessarily", "necessary", "need", "needs", "neither", "never", "nevertheless",
    "new", "next", "nine", "ninety", "nobody", "non", "none", "nonetheless", "noone", "normally",
    "nos", "noted", "nothing", "nowhere", "obtain", "obtained", "obviously", "often", "oh", "ok",
    "okay", "old", "omitted", "one", "ones", "onto", "ord", "others", "otherwise", "outside",
    "overall", "owing", "p", "page", "pages", "part", "particular", "particularly", "past", "per",
    "perhaps", "placed", "please", "plus", "poorly", "possible", "possibly", "potentially", "pp",
    "predominantly", "present", "previously", "primarily", "probably", "promptly", "proud",
    "provides", "put", "q", "que", "quickly", "quite", "qv", "r", "ran", "rather", "rd", "readily",
    "really", "recent", "recently", "ref", "refs", "regarding", "regardless", "regards", "related",
    "relatively", "research", "respectively", "resulted", "resulting", "results", "right", "run",
    "said", "saw", "say", "saying", "says", "sec", "section", "see", "seeing", "seem", "seemed",
    "seeming", "seems", "seen", "self", "selves", "sent", "seven", "several", "shall", "shed",
    "shes", "show", "showed", "shown", "showns", "shows", "significant", "significantly", "similar",
    "similarly", "since", "six", "slightly", "somebody", "somehow", "someone", "somethan",
    "something", "sometime", "sometimes", "somewhat", "somewhere", "soon", "sorry", "specifically",
    "specified", "specify", "specifying", "still", "stop", "strongly", "sub", "substantially",
    "successfully", "sufficiently", "suggest", "sup", "sure", "take", "taken", "taking", "tell",
    "tends", "th", "thank", "thanks", "thanx", "thats", "that've", "thence", "thereafter",
    "thereby", "thered", "therefore", "therein", "there'll", "thereof", "therere", "theres",
    "thereto", "thereupon", "there've", "theyd", "theyre", "think", "thou", "though", "thoughh",
    "thousand", "throug", "throughout", "thru", "thus", "til", "tip", "together", "took", "toward",
    "towards", "tried", "tries", "truly", "try", "trying", "ts", "twice", "two", "u", "un",
    "unfortunately", "unless", "unlike", "unlikely", "unto", "upon", "ups", "us", "use", "used",
    "useful", "usefully", "usefulness", "uses", "using", "usually", "v", "value", "various", "'ve",
    "via", "viz", "vol", "vols", "vs", "w", "want", "wants", "wasnt", "way", "wed", "welcome",
    "went", "werent", "whatever", "what'll", "whats", "whence", "whenever", "whereafter", "whereas",
    "whereby", "wherein", "wheres", "whereupon", "wherever", "whether", "whim", "whither", "whod",
    "whoever", "whole", "who'll", "whomever", "whos", "whose", "widely", "willing", "wish",
    "within", "without", "wont", "words", "world", "wouldnt", "www", "x", "yes", "yet", "youd",
    "youre", "z", "zero", "a's", "ain't", "allow", "allows", "apart", "appear", "appreciate",
    "appropriate", "associated", "best", "better", "c'mon", "c's", "cant", "changes", "clearly",
    "concerning", "consequently", "consider", "considering", "corresponding", "course", "currently",
    "definitely", "described", "despite", "entirely", "exactly", "example", "going", "greetings",
    "hello", "help", "hopefully", "ignored", "inasmuch", "indicate", "indicated", "indicates",
    "inner", "insofar", "it'd", "keep", "keeps", "novel", "presumably", "reasonably", "second",
    "secondly", "sensible", "serious", "seriously", "sure", "t's", "third", "thorough",
    "thoroughly", "three", "well", "wonder"
})


def _process_to_IDs_in_sparse_format(sp, sentences):
    """
    Method from https://tfhub.dev/google/universal-sentence-encoder-lite/2

    An utility method that processes sentences with the sentence piece processor
    'sp' and returns the results in tf.SparseTensor-similar format: (values, indices, dense_shape)
    """
    ids = [sp.EncodeAsIds(x) for x in sentences]
    max_len = max(len(x) for x in ids)
    dense_shape = (len(ids), max_len)
    values = [item for sublist in ids for item in sublist]
    indices = [[row, col] for row in range(len(ids)) for col in range(len(ids[row]))]
    return values, indices, dense_shape


def _clean_text(text):
    """
    General cleanup of anything that might not match a word.
    """
    if not text:  # if no text then skip processing
        return ''
    text = text.lower()
    text = text.replace('<i>', '')  # skip / clean anything related to html
    text = text.replace('<\\i>', '')  # skip / clean anything related to html

    text = re.sub(r"[^\w\-\'\s\.]", '',
                  text)  # remove all non name related characters (\w, '-' and "'")
    text = re.sub(r'\d|\_|\*', '', text)  # remove digits, '_' and '*' which are matched by \w
    text = re.sub(r'(^|\s+)-(\s+|$)', '', text)  # remove "-" when not used in between a word
    text = re.sub(r'\.+', ' ', text)  # remove "." when it's at the end of the sentence
    text = re.sub(r'\s+', ' ', text).strip()  # clean all extra spaces
    if text.count("'") > 1:
        text = re.sub(r'\'', '', text)
    return text


def _tokenizer(sentence: str) -> Iterable[str]:
    """
    Tokenize a sentence.
    TODO: Explore more advanced tokenization strategies (e.g. Spacy)
    """
    yield from sentence.split(' ')


def _remove_stopwords(sentence_tokens: Iterable[str]) -> Iterable[str]:
    """
    Exclude any stop word in the input set of tokens
    """
    yield from [x for x in sentence_tokens if x.lower() not in _STOPWORDS]


def process_content(sentence: str, terms_mapping: Optional[Dict[str, str]] = None) -> List[str]:
    """
    Process any input sentence using a dictionary of terms to be mapped, and returning
    a clean set of tokens excluding all stop words.
    """
    if terms_mapping:
        for term, mapping in terms_mapping.items():
            sentence = re.sub(rf'\b{term}\b', mapping, sentence, flags=re.I)
    return list(_remove_stopwords(_tokenizer(_clean_text(sentence))))


def load_embedding_model_lite(
        embeddings_path: Optional[str] = _EMBEDDINGS_PATH_LITE):  # pragma: no cover
    """
    Based on https://www.tensorflow.org/hub/tutorials/semantic_similarity_with_tf_hub_universal_encoder_lite
    """
    module = hub.Module(embeddings_path)
    with tf.Session() as sess:
        spm_path = sess.run(module(signature="spm_path"))

    sp = spm.SentencePieceProcessor()
    with tf.io.gfile.GFile(spm_path, mode="rb") as f:
        sp.LoadFromSerializedProto(f.read())
    return sp, module


def load_embedding_model(embeddings_path: Optional[str] = _EMBEDDINGS_PATH):  # pragma: no cover
    return hub.load(embeddings_path)


def group_sentences_lite(sp,
                         module,
                         sentences: List[str],
                         threshold: float = 0.5):  # pragma: no cover):
    """
    Method based on https://tfhub.dev/google/universal-sentence-encoder-lite/2
    """
    input_placeholder = tf.sparse_placeholder(tf.int64, shape=[None, None])
    encodings = module(inputs=dict(values=input_placeholder.values,
                                   indices=input_placeholder.indices,
                                   dense_shape=input_placeholder.dense_shape))

    values, indices, dense_shape = _process_to_IDs_in_sparse_format(sp, sentences)
    with tf.Session() as session:
        session.run([tf.global_variables_initializer(), tf.tables_initializer()])
        message_embeddings = session.run(encodings,
                                         feed_dict={
                                             input_placeholder.values: values,
                                             input_placeholder.indices: indices,
                                             input_placeholder.dense_shape: dense_shape
                                         })

        sparse_matrix = np.array(message_embeddings)
        return _group_sentences(sparse_matrix, threshold)


def group_sentences(embed_model, sentences: List[str], threshold: float = 0.5):  # pragma: no cover
    sparse_matrix = embed_model(sentences)['outputs']
    return _group_sentences(sparse_matrix.numpy(), threshold)


def _group_sentences(sparse_matrix, threshold):
    similarities = cosine_similarity(sparse_matrix)
    similar = np.where(similarities >= threshold)
    similar_sets = [(i, similar[1][similar[0] == i]) for i in np.unique(similar[0])]
    return similar_sets, remove_similar_subsets([x[1] for x in similar_sets])


def remove_subsets(all_sets):
    sets = sorted(all_sets, key=lambda x: len(x), reverse=False)
    final_sets = []
    for i, _ in enumerate(sets):
        skip = False
        for s in sets[i + 1:]:
            if not skip and len(set(sets[i]).difference(set(s))) == 0:
                final_sets.append(s)
                skip = True
        if not skip:
            final_sets.append(sets[i])
    return set(map(tuple, final_sets))


def _remove_similar_subsets(all_sets):
    sets = sorted(all_sets, key=lambda x: len(x), reverse=False)
    final_sets = []
    for i, _ in enumerate(sets):
        skip = False
        for s in sets[i + 1:]:
            if not skip and len(set(sets[i]).intersection(set(s))) > 0:
                final_sets.append(sorted(set(sets[i]).union(set(s))))
                skip = True
        if not skip:
            final_sets.append(sorted(sets[i]))
    return set(map(tuple, final_sets))


def remove_similar_subsets(all_sets):
    if not all_sets:
        return set(all_sets)
    while True:
        output = _remove_similar_subsets(all_sets)
        if _compare_sets(output, all_sets):
            break
        all_sets = output
    return all_sets


def _compare_sets(set1, set2):
    sset1 = sorted([sorted(x) for x in set1])
    sset2 = sorted([sorted(x) for x in set2])
    return sset1 == sset2


def get_top_words(sentences: List[str], top_n: int = 10) -> List[Tuple[str, int]]:
    words = Counter()
    for sentence in sentences:
        words.update(process_content(sentence))
    return sorted(words.items(), key=lambda x: x[1], reverse=True)[:top_n]
