# News Grouping Algorithm

This document describes the hierarchical clustering algorithm used by Newvelles to group and organize news articles from RSS feeds.

## Overview

The algorithm creates a **hierarchical structure** with three levels:
1. **Top-level groups** - Major topic clusters (e.g., "Phones of 2026")
2. **Lower-level groups** - Sub-topics within each major cluster (e.g., "Best Android Phones")
3. **Individual articles** - The actual news entries

The algorithm uses **TF-IDF vectorization** and **cosine similarity** to measure article similarity, avoiding the need for heavy machine learning models or external APIs.

## Algorithm Pipeline

```
RSS Feeds → Text Preprocessing → Level 1: Group Similar Titles →
Level 2: Cluster Groups → Extract Group Identifiers → Rank Groups → Final Visualization
```

---

## Step 1: Text Preprocessing

**Location:** `newvelles/utils/text.py`
**Function:** `process_content()`

### Purpose
Clean and normalize text before similarity analysis to improve matching accuracy.

### Process

#### 1.1 Clean Text (`_clean_text()`)
- Convert to lowercase
- Remove HTML tags (`<i>`, `</i>`, etc.)
- Remove non-word characters except hyphens, apostrophes, spaces, periods
- Remove digits, underscores, asterisks
- Clean up excessive spaces and punctuation
- Remove excessive apostrophes

**Example:**
```python
Input:  "Apple's iPhone 15 Pro - $999!"
Output: "apples iphone pro"
```

#### 1.2 Tokenize (`_tokenizer()`)
- Split on whitespace

**Example:**
```python
Input:  "apples iphone pro"
Output: ["apples", "iphone", "pro"]
```

#### 1.3 Remove Stopwords (`_remove_stopwords()`)
- Filter out 179 common words (a, an, the, is, are, was, etc.)
- Keeps only meaningful content words

**Example:**
```python
Input:  ["the", "new", "iphone", "is", "here"]
Output: ["new", "iphone", "here"]
```

### Result
A clean list of meaningful tokens ready for similarity comparison.

---

## Step 2: Level 1 Grouping - Similar Titles

**Location:** `newvelles/models/grouping.py`
**Function:** `group_similar_titles()`

### Purpose
Find articles about the same specific story or topic.

### Algorithm

1. **Preprocess all titles** using `process_content()`
2. **Create TF-IDF vectors** using sklearn's `TfidfVectorizer`
   - **TF-IDF** (Term Frequency - Inverse Document Frequency) weights words by:
     - **TF**: How often they appear in a document
     - **IDF**: How rare they are across all documents
   - Result: Rare, meaningful words get higher weights

3. **Compute cosine similarity matrix**
   - Measures similarity between 0 (unrelated) and 1 (identical)
   - Cosine similarity = angle between two vectors in high-dimensional space
   - Formula: `similarity(A, B) = (A · B) / (||A|| × ||B||)`

4. **Group titles with similarity ≥ 0.7** (default threshold)
   - Iterate through titles sequentially
   - For each title, find all subsequent similar titles
   - Create groups, avoiding duplicates using a `used_indices` set
   - **Filter out groups with < 2 titles** (singletons aren't interesting)

### Example

```python
Input titles:
- "Best Android Phones of 2026"
- "9 Best Android Phones Tested and Reviewed"
- "Trump announces new policy"

After preprocessing:
- ["best", "android", "phones"]
- ["best", "android", "phones", "tested", "reviewed"]
- ["trump", "announces", "policy"]

Similarity matrix:
         Title1  Title2  Title3
Title1:  1.00    0.82    0.05
Title2:  0.82    1.00    0.03
Title3:  0.05    0.03    1.00

Result:
Group 1: [Title1, Title2]  # Similar Android phone articles (0.82 ≥ 0.7)
Title3: Excluded (singleton - no similar articles)
```

### Parameters
- `similarity_threshold`: Default 0.7
- Higher values = stricter matching (fewer, tighter groups)
- Lower values = looser matching (more, broader groups)

---

## Step 3: Level 2 Clustering - Context Grouping

**Location:** `newvelles/models/grouping.py`
**Function:** `cluster_groups()`

### Purpose
Cluster related groups into higher-level topics to create the top-level hierarchy.

### Algorithm

1. **Create group representations**
   - Concatenate all titles within each group
   - Preprocess the combined text

   **Example:**
   ```python
   Group 1: ["Best Android Phones", "Top Android Devices"]
   → Combined: "best android phones top android devices"
   → Processed: ["best", "android", "phones", "top", "devices"]
   ```

2. **Compute TF-IDF for group representations**
   - Each group becomes a single "document"
   - TF-IDF vectorization applied to group-level text

3. **Compute cosine similarity between groups**
   - Same similarity measure as Level 1
   - But comparing groups instead of individual titles

4. **Cluster groups with similarity ≥ 0.5** (context threshold)
   - Lower threshold than Level 1 (more permissive)
   - Allows related but not identical topics to cluster together
   - Creates "top-level groups"

### Example

```python
Group A: Android phone articles
Group B: iPhone articles
Group C: Samsung Galaxy articles
Group D: Political news

Similarity matrix:
       A     B     C     D
A:   1.00  0.65  0.72  0.02
B:   0.65  1.00  0.58  0.01
C:   0.72  0.58  1.00  0.03
D:   0.02  0.01  0.03  1.00

Result:
Top-level Group 1: [A, B, C]  # All phone-related (similarities ≥ 0.5)
Top-level Group 2: [D]         # Political news (no similar groups)
```

### Parameters
- `context_similarity_threshold`: Default 0.5
- Lower than Level 1 to allow broader topic grouping
- Balances between too fragmented vs too broad

---

## Step 4: Extract Group Identifiers

**Location:** `newvelles/models/grouping.py`
**Functions:** `identify_group()`, `extract_common_substrings()`

### Purpose
Create human-readable labels for groups based on shared text patterns.

### Algorithm

#### 4.1 Find Common Substrings (`extract_common_substrings()`)
1. Compare all title pairs within a group
2. Find all substrings ≥ 3 characters appearing in multiple titles
3. Build a set of all common substrings
4. Sort by length (longest first)

**Example:**
```python
Titles in group:
- "Best Android Phones of 2026, Tested and Reviewed"
- "9 Best Android Phones of 2026"

Common substrings found:
- "Best Android Phones of 2026" (27 chars)
- "Best Android Phones" (18 chars)
- "Android Phones of 2026" (22 chars)
- "Android Phones" (14 chars)
- " of 2026" (8 chars)
- "Best" (4 chars)
- ... (many more)

Sorted by length (descending):
1. "Best Android Phones of 2026"
2. "Android Phones of 2026"
3. "Best Android Phones"
...
```

#### 4.2 Create Identifier (`identify_group()`)
- Take top 3 common substrings (by length)
- Concatenate with spaces

**Example:**
```python
Top 3 common substrings:
1. "Best Android Phones of 2026"
2. "Android Phones of 2026"
3. "Best Android Phones"

Group identifier:
"Best Android Phones of 2026 Android Phones of 2026 Best Android Phones"
```

### Parameters
- `min_length`: Default 3 characters
- Number of substrings used: 3 (hardcoded in `identify_group()`)

### Limitations
- Can create verbose or redundant labels
- May not always capture the most meaningful summary
- Future improvement: Use spaCy NLP to extract key nouns/verbs (see commented code in `grouping.py`)

---

## Step 5: Build Visualization

**Location:** `newvelles/models/grouping.py`
**Function:** `build_visualization()`

### Purpose
Create the final hierarchical JSON structure for web visualization.

### Process

1. Extract all titles from input data (`title_data`)
2. Run `build_news_groups()` which executes:
   - Level 1 grouping (`group_similar_titles()`)
   - Level 2 clustering (`cluster_groups()`)
   - Group identification (`identify_group()`)

3. Build nested dictionary structure:
   ```json
   {
     "Top-level identifier": {
       "Lower-level identifier": {
         "Article title": {
           "title": "Full article title",
           "link": "https://...",
           "timestamp": "Fri, 06 Mar 2026 18:00:00 +0000",
           "source": "https://source-rss-feed.com"
         }
       }
     }
   }
   ```

4. Convert `defaultdict` to regular `dict` for JSON serialization
5. **Apply ranking** using `rank_news_groups()` to sort groups by importance

### Output Schema
- **Version**: 0.2.1 (defined in `VISUALIZATION_VERSION`)
- **Schema file**: `schemas/latest_news_schema.json`
- Three-level nested structure (top → lower → articles)
- Groups are sorted by ranking rules (most important first)

---

## Step 6: Rank Groups

**Location:** `newvelles/models/grouping.py`
**Function:** `rank_news_groups()`

### Purpose
Sort news groups by importance to surface the most significant stories first in the visualization.

### Algorithm

The ranking uses a **tuple-based sorting key** with 4 criteria (in priority order):

```python
ranking_key = (
    -is_multi_phrase,    # 1. Multi-phrase groups first
    -word_count,         # 2. More words in phrase first (single-phrase only)
    -sub_group_count,    # 3. More sub-groups first
    -total_news          # 4. More news items first
)
```

Negative values ensure descending sort (higher values = higher rank).

### Ranking Rules

#### Rule 1: Multi-phrase vs Single-phrase Groups
- **Multi-phrase groups** (2+ top-level phrases) rank **HIGHER**
- **Single-phrase groups** (1 top-level phrase) rank **LOWER**

**Example:**
```
✅ Higher rank: "[war impedes] [Iran War] [Oil prices]" (3 phrases)
❌ Lower rank: "[Berkshire Hathaway]" (1 phrase)
```

#### Rule 2: Word Count in Single-Phrase Groups
- **For single-phrase groups only**: Multi-word phrases rank **HIGHER** than single-word phrases
- Multi-phrase groups are unaffected (word_count = 999)

**Example:**
```
✅ Higher rank: "[housing vouchers]" (2 words)
❌ Lower rank: "[Sleep]" (1 word)
```

**Rationale**: Single-word groups like `[Car]`, `[Sleep]`, `[Art]` are often too generic or trivial to be interesting top-level topics.

#### Rule 3: Sub-grouping Count
- More sub-groupings indicate richer, multi-faceted topics
- Groups with diverse sub-topics rank higher

**Example:**
```
✅ Higher rank: Group with 9 sub-groupings (diverse topic)
❌ Lower rank: Group with 1 sub-grouping (narrow topic)
```

#### Rule 4: Total News Count
- More news items indicate broader coverage or higher activity
- Breaking news often generates many articles

**Example:**
```
✅ Higher rank: 38 news items (high activity)
❌ Lower rank: 2 news items (limited coverage)
```

### Ranking Tiers

The algorithm creates a natural hierarchy of news importance:

```
┌─────────────────────────────────────────────────────┐
│ Tier 1: Multi-phrase Groups (Highest Priority)     │
│  • 3+ phrases, many sub-groups, many news items    │
│  • Example: [war] [Iran] [Oil prices]              │
│  • Major, complex, ongoing stories                 │
└─────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│ Tier 2: Multi-phrase Groups (Moderate Priority)    │
│  • 2+ phrases, fewer sub-groups or news            │
│  • Example: [banks] [crypto]                       │
│  • Related topics with limited coverage            │
└─────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│ Tier 3: Multi-word Single-phrase Groups            │
│  • 1 phrase, 2+ words, some sub-groups/news        │
│  • Example: [Novo Nordisk], [housing vouchers]    │
│  • Specific topics with moderate interest          │
└─────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│ Tier 4: Single-word Groups (Lowest Priority)       │
│  • 1 phrase, 1 word, minimal content               │
│  • Example: [Sleep], [Car], [Art]                 │
│  • Generic or trivial topics                       │
└─────────────────────────────────────────────────────┘
```

### Example

```python
Input groups (unranked):
{
  "[Sleep]": {                    # 1 phrase, 1 word, 1 sub, 3 news
    "[Sleep]": [news1, news2, news3]
  },
  "[Novo Nordisk]": {             # 1 phrase, 2 words, 1 sub, 3 news
    "[Novo Nordisk]": [news1, news2, news3]
  },
  "[war] [Iran] [Oil]": {         # 3 phrases, 9 subs, 38 news
    "[Oil Prices]": [news1, ...],
    "[war impedes]": [news4, ...],
    ... (7 more sub-groups)
  },
  "[banks] [crypto]": {           # 2 phrases, 1 sub, 2 news
    "[crypto]": [news1, news2]
  }
}

After ranking:
1. [war] [Iran] [Oil]        → (-1, -999, -9, -38)   # Tier 1
2. [banks] [crypto]          → (-1, -999, -1, -2)    # Tier 2
3. [Novo Nordisk]            → (0, -2, -1, -3)       # Tier 3
4. [Sleep]                   → (0, -1, -1, -3)       # Tier 4
```

### Performance
- **Time complexity**: O(n log n) for sorting
- **Typical time**: <1ms for ~200 groups
- **Memory**: Negligible (creates sorting tuples only)

### Integration
`rank_news_groups()` is called in `build_visualization()` after all grouping and identification is complete, just before returning the final structure.

---

## Complete Example

### Input RSS Feeds

```
1. "Apple announces iPhone 16 with AI features"
2. "New iPhone 16 Pro features announced by Apple"
3. "Samsung Galaxy S26 launched with camera upgrades"
4. "Galaxy S26 vs S25: Camera comparison"
5. "Biden signs infrastructure bill into law"
6. "Senate passes infrastructure spending bill"
```

### After Preprocessing

```python
1. ["apple", "announces", "iphone", "ai", "features"]
2. ["iphone", "pro", "features", "announced", "apple"]
3. ["samsung", "galaxy", "launched", "camera", "upgrades"]
4. ["galaxy", "comparison", "camera"]
5. ["biden", "signs", "infrastructure", "bill", "law"]
6. ["senate", "passes", "infrastructure", "spending", "bill"]
```

### Level 1 Groups (similarity ≥ 0.7)

```
Group A: [1, 2] - iPhone announcements
  Similarity: 0.85 (shared: "iphone", "features", "apple")

Group B: [3, 4] - Samsung Galaxy
  Similarity: 0.78 (shared: "galaxy", "camera")

Group C: [5, 6] - Infrastructure bills
  Similarity: 0.72 (shared: "infrastructure", "bill")
```

### Level 2 Top-Level Groups (similarity ≥ 0.5)

```
Top Group 1: [A, B] - Phone announcements
  Similarity: 0.62 (both about phone products)

Top Group 2: [C] - Political news
  No similar groups (tech similarity to Group 1: 0.08)
```

### Final Visualization Output

```json
{
  "iPhone announces Samsung Galaxy": {
    "iPhone announces features": {
      "Apple announces iPhone 16 with AI features": {
        "title": "Apple announces iPhone 16 with AI features",
        "link": "https://...",
        "timestamp": "Fri, 06 Mar 2026 10:00:00 +0000",
        "source": "https://techcrunch.com/feed"
      },
      "New iPhone 16 Pro features announced by Apple": {
        "title": "New iPhone 16 Pro features announced by Apple",
        "link": "https://...",
        "timestamp": "Fri, 06 Mar 2026 11:30:00 +0000",
        "source": "https://wired.com/feed"
      }
    },
    "Samsung Galaxy camera": {
      "Samsung Galaxy S26 launched with camera upgrades": {
        "title": "Samsung Galaxy S26 launched with camera upgrades",
        "link": "https://...",
        "timestamp": "Fri, 06 Mar 2026 09:00:00 +0000",
        "source": "https://theverge.com/feed"
      },
      "Galaxy S26 vs S25: Camera comparison": {
        "title": "Galaxy S26 vs S25: Camera comparison",
        "link": "https://...",
        "timestamp": "Fri, 06 Mar 2026 12:00:00 +0000",
        "source": "https://cnet.com/feed"
      }
    }
  },
  "infrastructure bill": {
    "infrastructure bill": {
      "Biden signs infrastructure bill into law": {
        "title": "Biden signs infrastructure bill into law",
        "link": "https://...",
        "timestamp": "Fri, 06 Mar 2026 14:00:00 +0000",
        "source": "https://nytimes.com/feed"
      },
      "Senate passes infrastructure spending bill": {
        "title": "Senate passes infrastructure spending bill",
        "link": "https://...",
        "timestamp": "Thu, 05 Mar 2026 16:00:00 +0000",
        "source": "https://washingtonpost.com/feed"
      }
    }
  }
}
```

---

## Key Parameters Summary

| Parameter | Default | Location | Purpose |
|-----------|---------|----------|---------|
| `DEFAULT_SIMILARITY_THRESHOLD` | 0.25 | `group_similar_titles()` | Level 1 title grouping threshold |
| `DEFAULT_CONTEXT_SIMILARITY_THRESHOLD` | 0.2 | `cluster_groups()` | Level 2 group clustering threshold |
| `MIN_SUBSTRING_LENGTH` | 3 | `extract_common_substrings()` | Minimum substring length for identifiers |
| `MAX_SUBSTRING_WORDS` | 5 | `identify_group()` | Maximum words per substring |
| `TOP_SUBSTRINGS_LIMIT` | 3 | `identify_group()` | Number of substrings for group identifier |
| `OVERLAP_FILTER_THRESHOLD` | 0.5 | `_filter_highly_overlapping_phrases()` | Word overlap threshold for filtering redundant phrases |
| `MIN_GROUP_SIZE` | 2 | `group_similar_titles()` | Minimum articles per group (filters singletons) |

**Note**: Lower thresholds (0.25, 0.2) were adopted to create broader, more inclusive groupings compared to the original strict thresholds (0.7, 0.5).

---

## Algorithm Characteristics

### Strengths

✅ **Fast and deterministic**
- TF-IDF is lightweight and doesn't require GPU
- No API calls or external services needed
- Consistent results for same input

✅ **Works offline**
- No internet connection required after initial RSS fetch
- Suitable for Lambda environment with limited network

✅ **Two-level hierarchy**
- Provides intuitive organization
- Major topics → Sub-topics → Articles
- Easy to visualize in web UI

✅ **Scalable**
- Handles 100+ articles efficiently
- O(n²) complexity manageable for typical RSS volumes

✅ **Configurable thresholds**
- Easy to tune grouping behavior
- No model retraining required

✅ **Smart ranking**
- Surfaces important stories first
- Multi-tier priority system
- Filters out trivial single-word topics
- Balances breadth (phrase count), diversity (sub-groups), and activity (news count)

✅ **Case-insensitive phrase filtering**
- Removes redundant phrases differing only in case
- Example: "[Oil Prices Surge]" and "[oil prices surge]" treated as duplicates
- Cleaner, more professional group identifiers

### Limitations

⚠️ **TF-IDF limitations**
- Captures word frequency, not semantic meaning
- "bank" (river) vs "bank" (money) treated identically
- Cannot understand synonyms ("car" vs "automobile")
- Sensitive to exact word matches

⚠️ **Group identifier issues**
- Common substring extraction can create verbose labels
- May produce redundant or unclear identifiers
- Example: "Best Phones Best Phones of 2026"

⚠️ **Fixed thresholds**
- Single threshold may not work well for all news types
- Sports news might need different threshold than tech news
- No adaptive threshold adjustment

⚠️ **Single-pass clustering**
- No iterative refinement
- Greedy approach may not find globally optimal grouping
- Order-dependent (processes titles sequentially)

⚠️ **No cross-feed deduplication**
- Same story from multiple RSS feeds creates separate articles
- Relies on title similarity, not content analysis

### Future Improvements

The codebase contains commented-out sections (lines 17-20, 208-313 in `grouping.py`) showing legacy embedding-based approaches:

1. **Universal Sentence Encoder (USE)**
   - Better semantic understanding
   - Understands "car" ≈ "automobile"
   - More computationally expensive
   - Requires TensorFlow

2. **spaCy-based group headers** (commented in line 186)
   - Extract key nouns and verbs using NLP
   - Create more meaningful group identifiers
   - Already partially implemented in `utils/text.py`

3. **Adaptive thresholds**
   - Learn optimal thresholds based on feed characteristics
   - Different thresholds per news category

---

## Implementation Files

| File | Functions | Purpose |
|------|-----------|---------|
| `newvelles/models/grouping.py` | `group_similar_titles()` | Level 1: Group similar titles |
| | `cluster_groups()` | Level 2: Cluster groups |
| | `extract_common_substrings()` | Find common text patterns |
| | `_filter_highly_overlapping_phrases()` | Filter redundant phrases (case-insensitive) |
| | `identify_group()` | Create group identifiers |
| | `rank_news_groups()` | **Rank groups by importance** |
| | `build_news_groups()` | Orchestrate grouping pipeline |
| | `build_visualization()` | Create final JSON output with ranking |
| `newvelles/utils/text.py` | `process_content()` | Text preprocessing pipeline |
| | `_clean_text()` | Text cleaning |
| | `_tokenizer()` | Tokenization |
| | `_remove_stopwords()` | Stopword filtering |
| | `get_sentence_score()` | Score sentences for ranking |
| | `remove_stopwords()` | Public stopword removal function |

---

## Testing

Unit tests for the grouping algorithm are located in multiple test files:

**`test/test_models_grouping.py`:**
- `TestGroupSimilarTitles` - Level 1 grouping tests
- `TestClusterGroups` - Level 2 clustering tests
- `TestExtractCommonSubstrings` - Substring extraction tests
- `TestIdentifyGroup` - Group identifier tests
- `TestBuildNewsGroups` - Integration tests
- `TestBuildVisualization` - End-to-end visualization tests

**`test/test_group_identifier_improved.py`:**
- Case-insensitive phrase filtering tests
- Word boundary detection tests
- Overlapping phrase removal tests

**`test/test_group_ranking.py`:**
- `test_ranking_rules_from_latest_news` - Validates all ranking rules
- `test_expected_order_from_sample` - Tests specific expected order
- `test_single_word_phrases_rank_lowest` - Validates word-count ranking

**`test/test_end_to_end_grouping.py`:**
- End-to-end tests with real news data

Run tests:
```bash
pytest test/test_models_grouping.py -v
pytest test/test_group_ranking.py -v
pytest test/ -k "not test_integration" -q  # All non-integration tests
```

Current test results: **200 passing** (including 3 ranking tests)

---

## Configuration

The grouping behavior can be tuned via:

1. **Code parameters** (in function calls):
   - `similarity_threshold` in `group_similar_titles()`
   - `context_similarity_threshold` in `cluster_groups()`
   - `min_length` in `extract_common_substrings()`

2. **Config file** (`newvelles/config/newvelles.ini`):
   ```ini
   [PARAMS]
   cluster_limit: 1  # Minimum articles per group
   ```

3. **Environment variables**:
   - No environment-specific configuration currently
   - Algorithm behaves identically in local/QA/production

---

## Performance Characteristics

For typical RSS processing (84 feeds, ~500 articles):

- **Preprocessing**: ~2-5 seconds
- **Level 1 grouping**: ~3-8 seconds (TF-IDF + similarity matrix)
- **Level 2 clustering**: ~1-3 seconds
- **Group identification**: <1 second
- **Total**: ~10-20 seconds

Memory usage: ~50-100 MB (mostly for TF-IDF matrices)

Bottlenecks:
- Cosine similarity matrix computation (O(n²))
- TF-IDF vectorization for large vocabularies

---

## References

- **TF-IDF**: [Wikipedia](https://en.wikipedia.org/wiki/Tf%E2%80%93idf)
- **Cosine Similarity**: [Wikipedia](https://en.wikipedia.org/wiki/Cosine_similarity)
- **scikit-learn TfidfVectorizer**: [Documentation](https://scikit-learn.org/stable/modules/generated/sklearn.feature_extraction.text.TfidfVectorizer.html)
- **Universal Sentence Encoder** (legacy): [TensorFlow Hub](https://tfhub.dev/google/universal-sentence-encoder/4)
