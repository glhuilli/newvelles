# News Group Ranking Implementation Plan

**Status:** ✅ **IMPLEMENTED** (2026-03-11)

## Problem Statement

Previously, news groups in `latest_news.json` were not properly ranked. Groups with minimal content (1 phrase, 1 sub-grouping, 2 news) appeared at the top, while rich groups with multiple sub-groupings and many news items appeared lower.

## Current State Analysis

From `latest_news.json`:
- **Position 1**: `[Berkshire Hathaway]` - 1 phrase, 1 sub-group, 2 news ❌ (should be at bottom)
- **Position 2**: `[war impedes...] [Iran War...] [Oil gas...]` - 3 phrases, 9 sub-groups, 38 news ✅ (should be at top)
- **Position 8**: `[Lifts PT]` - 1 phrase, 1 sub-group, 2 news ❌ (should be at bottom)
- **Position 9**: `[Novo Nordisk]` - 1 phrase, 1 sub-group, 2 news ❌ (should be at bottom)

## Ranking Rules (Priority Order)

### Rule 1: Multi-phrase vs Single-phrase
- **Multi-phrase groups** (2+ top-level phrases) rank **HIGHER**
- **Single-phrase groups** (1 top-level phrase) rank **LOWER**

### Rule 2: Word Count in Single-Phrase Groups
- **For single-phrase groups only**: Multi-word phrases rank **HIGHER** than single-word phrases
- Example: `[housing vouchers]` (2 words) > `[Sleep]` (1 word)
- Example: `[Berkshire Hathaway]` (2 words) > `[Car]` (1 word)
- Multi-phrase groups are unaffected by this rule (word count doesn't apply)

### Rule 3: Within Each Category - Sub-grouping Count
- More sub-groupings rank higher than fewer sub-groupings
- Example: 9 sub-groups > 2 sub-groups > 1 sub-group

### Rule 4: Within Each Category - Total News Count
- More news items rank higher than fewer news items
- Example: 38 news > 11 news > 4 news > 2 news

### Rule 5: Very Bottom Placement
- Groups with **1 word + 1 phrase + 1 sub-group + 2 news** go to the very bottom
- These are considered the least significant/interesting (e.g., `[Sleep]`, `[Car]`, `[Art]`)

## Implementation Strategy

### Step 1: Create Ranking Function

Create `rank_news_groups()` in `newvelles/models/grouping.py`:

```python
def rank_news_groups(groups: Dict[str, Dict[str, Dict]]) -> Dict[str, Dict[str, Dict]]:
    """
    Rank/sort news groups according to priority rules.

    Args:
        groups: Dictionary of news groups (top-level -> sub-groups -> articles)

    Returns:
        OrderedDict of groups sorted by ranking priority
    """

    def get_ranking_key(item):
        top_group_id, sub_groups = item

        # Count top-level phrases (phrases between brackets)
        phrase_count = len([p.strip()
                           for p in top_group_id.replace('[', '|').replace(']', '').split('|')
                           if p.strip()])

        # Count sub-groupings
        sub_group_count = len(sub_groups)

        # Count total news items
        total_news = sum(len(articles) for articles in sub_groups.values())

        # Multi-phrase groups rank higher (use negative to sort descending)
        is_multi_phrase = 1 if phrase_count > 1 else 0

        # For single-phrase groups, count words in the phrase
        # Multi-word phrases rank higher than single-word phrases
        if phrase_count == 1:
            word_count = len(top_group_id.replace('[', '').replace(']', '').strip().split())
        else:
            word_count = 999  # Large value so multi-phrase groups are unaffected

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
```

### Step 2: Integrate with Visualization Functions

Modify `build_visualization()` and `build_visualization_lite()` to call `rank_news_groups()` before returning:

```python
def build_visualization(title_data, cluster_limit=0):
    # ... existing code ...

    result_dict = _convert_defaultdict_to_dict(visualization)

    # Apply ranking before returning
    result_dict = rank_news_groups(result_dict)

    return result_dict, {}
```

### Step 3: Test Integration

1. Run unit tests in `test/test_group_ranking.py`
2. Verify `latest_news.json` structure is properly ranked after regeneration
3. Ensure no logic changes to grouping algorithm, only sorting

## Expected Outcome

After implementation, `latest_news.json` should have:

**Top Groups** (Multi-phrase with many sub-groups/news):
1. `[war impedes...] [Iran War...] [Oil gas...]` - 3 phrases, 9 subs, 38 news
2. `[CD rates...] [high-yield savings...] [2026 Lock...]` - 3 phrases, 2 subs, 11 news
3. `[markets] [calm] [prices]` - 3 phrases, 2 subs, 4 news
4. ... other multi-phrase groups ...

**Bottom Groups** (Single-phrase with minimal content):
- ... other single-phrase groups ...
- `[Novo Nordisk]` - 1 phrase, 1 sub, 3 news
- `[Berkshire Hathaway]` - 1 phrase, 1 sub, 2 news
- `[Lifts PT]` - 1 phrase, 1 sub, 2 news

## Testing Strategy

1. **Unit tests** - `test/test_group_ranking.py` validates ranking logic
2. **Integration test** - Verify actual `latest_news.json` follows expected order
3. **Regression test** - Ensure no breaking changes to group identification

## Rollback Plan

If issues arise:
1. Ranking function is isolated and can be removed
2. Visualization functions have minimal changes
3. Tests can be marked as `@pytest.mark.skip` temporarily

---

## Implementation Complete ✅

### Test Results
- **All ranking tests**: 3/3 passing
- **Full test suite**: 200/200 passing
- **Test files**: `test/test_group_ranking.py`

### Actual Results (Using latest_news.json)

**Top 5 Groups** (Multi-phrase with rich content):
```
1. [war impedes production shipping] [barrel Iran war] [Oil gas prices]
   → 3 phrases, 9 sub-groups, 29 news

2. [attacks Israel Gulf states] [Mojtaba Khamenei Irans Supreme] [naming leader Day...]
   → 3 phrases, 7 sub-groups, 32 news

3. [Washington Heights] [shot fight] [North Lawndale]
   → 3 phrases, 4 sub-groups, 14 news

4. [Anthropic supply chain risk] [red lines] [AI company]
   → 3 phrases, 4 sub-groups, 13 news

5. [adviser Stephen Miller] [NYC Mayors House] [White Sox]
   → 3 phrases, 4 sub-groups, 11 news
```

**Bottom 10 Groups** (Single-phrase with minimal content):
```
189-198 (all single-phrase with 1 sub-group and 2-3 news items)
  - Positions 189-180: Multi-word single-phrase groups (e.g., [housing vouchers], [San Jose])
  - Positions 181-198: Single-word groups (e.g., [Sleep], [Car], [Art], [Prime])
```

### Key Improvements
1. ✅ Multi-phrase groups now rank at the top
2. ✅ Single-word phrases rank at the very bottom (positions 181-198)
3. ✅ Multi-word single-phrase groups rank above single-word groups
4. ✅ Within each tier, groups sorted by sub-group count then news count
5. ✅ Rich, multi-faceted news topics get proper visibility
