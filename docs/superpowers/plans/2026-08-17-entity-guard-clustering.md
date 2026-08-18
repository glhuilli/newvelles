# Entity-Guarded Context Clustering Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop `cluster_groups` from merging different real-world stories that share event-type vocabulary (e.g., three unrelated murder trials) by requiring named-entity agreement in addition to TF-IDF similarity.

**Architecture:** A per-group entity-token extractor (spaCy NER, PERSON+ORG labels, word-level lowercase tokens) runs once per subgroup inside `cluster_groups`. A merge now requires cosine ≥ 0.2 **and** entity compatibility: if both groups have PERSON/ORG entities, their token sets must intersect; if either has none, cosine alone decides (preserves behavior for entity-less headlines). Downstream (stories, momentum, naming) is untouched — it just receives correctly split clusters.

**Tech Stack:** spaCy `en_core_web_sm` (already loaded as `NLP` in `newvelles/utils/text.py`), scikit-learn TF-IDF (unchanged).

**Spec:** Conversation 2026-08-17 — diagnosis confirmed with live prod data: top-level group `[Tupac Shakur murder trial] [Luigi Mangiones York] [Lindsay Clancy]` contained 4 clean subgroups of 3 distinct trials; merge happens at level 2 because corpus-wide IDF makes shared courtroom vocabulary distinctive while nothing checks entities. Verified repro: with filler corpus, `cluster_groups` merges the Tupac and Mangione groups. Decision: fix the split rather than umbrella-title the mixed cluster.

## Global Constraints

- ~~PERSON and ORG labels only~~ **Revised during Task 1:** `en_core_web_sm` mislabels people ("Tupac Shakur" → NORP, "Tupac Shakur's" → GPE), so the guard uses the broad label set {PERSON, ORG, GPE, LOC, NORP, FAC, EVENT} (same as stories.py). Safe because extra shared tokens only relax the guard back to similarity-only merging — the guard can reduce false merges but never adds one.
- Entity extraction per title (not on concatenated group text — run-on text degrades NER).
- Word-level token matching, lowercase, alphabetic tokens ≥ 3 chars, stop-words dropped ("Tupac" matches "Tupac Shakur"; possessive "'s" never blocks).
- If either group has no PERSON/ORG entities → fall back to cosine-only (never make entity-less groups unmergeable).
- No signature changes visible to callers of `build_news_groups` / `build_visualization`.
- `make test` (449 tests) must stay green; if an existing grouping test asserted a merge the guard now correctly blocks, examine whether the test encoded the bug — fix the test only with justification.

---

### Task 1: entity token extraction + compatibility (pure helpers)

**Files:**
- Modify: `newvelles/models/grouping.py` (add `_entity_tokens`, `_entities_compatible`, `_GUARD_ENTITY_LABELS`)
- Test: `test/test_models_grouping.py` (append `TestEntityGuardHelpers`)

**Interfaces:**
- Produces: `_entity_tokens(titles: List[str]) -> Set[str]`; `_entities_compatible(tokens_a: Set[str], tokens_b: Set[str]) -> bool`.

- [ ] **Step 1: failing tests** (append to `test/test_models_grouping.py`)

```python
class TestEntityGuardHelpers:
    def test_entity_tokens_extracts_person_word_tokens(self):
        tokens = _entity_tokens(["Opening statements begin in Tupac Shakur murder trial"])
        assert "tupac" in tokens and "shakur" in tokens

    def test_entity_tokens_ignores_places(self):
        tokens = _entity_tokens(["Hurricane nears Florida coast"])
        assert "florida" not in tokens

    def test_entities_compatible_requires_overlap_when_both_present(self):
        assert _entities_compatible({"tupac", "shakur"}, {"tupac"}) is True
        assert _entities_compatible({"tupac", "shakur"}, {"luigi", "mangione"}) is False

    def test_entities_compatible_falls_back_when_either_empty(self):
        assert _entities_compatible(set(), {"luigi"}) is True
        assert _entities_compatible({"tupac"}, set()) is True
        assert _entities_compatible(set(), set()) is True
```

- [ ] **Step 2: run — FAIL** (`pytest test/test_models_grouping.py -k EntityGuard -v`, ImportError)
- [ ] **Step 3: implement** in `grouping.py` (import `NLP` from `newvelles.utils.text`):

```python
_GUARD_ENTITY_LABELS = {"PERSON", "ORG"}


def _entity_tokens(titles: List[str]) -> Set[str]:
    """Word-level PERSON/ORG entity tokens for a group of titles."""
    tokens: Set[str] = set()
    for title in titles:
        for ent in NLP(title).ents:
            if ent.label_ not in _GUARD_ENTITY_LABELS:
                continue
            for tok in ent:
                if tok.is_alpha and not tok.is_stop and len(tok.text) >= 3:
                    tokens.add(tok.text.lower())
    return tokens


def _entities_compatible(tokens_a: Set[str], tokens_b: Set[str]) -> bool:
    """Two groups may merge only if their entity tokens intersect.

    Groups without PERSON/ORG entities can't be discriminated by entities,
    so they fall back to similarity-only merging.
    """
    if not tokens_a or not tokens_b:
        return True
    return bool(tokens_a & tokens_b)
```

- [ ] **Step 4: run — PASS**
- [ ] **Step 5: commit** (`feat: entity token helpers for context-merge guard`)

### Task 2: wire guard into `cluster_groups` + regression test

**Files:**
- Modify: `newvelles/models/grouping.py` (`cluster_groups`)
- Test: `test/test_models_grouping.py` (append `TestEntityGuardedClustering` — the verified repro)

- [ ] **Step 1: failing regression test** — the verified reproduction: 9 trial titles (Tupac ×4, Mangione ×3, Clancy ×2) + 24 filler titles (8 unrelated topics × 3 paraphrases, no courtroom vocabulary). Assert no top-level cluster contains two different trial defendants. (Full title list from the 2026-08-17 session repro; currently produces `['tupac', 'mangione']` in one cluster.)
- [ ] **Step 2: run — FAIL** (tupac+mangione merged)
- [ ] **Step 3: implement** — in `cluster_groups`, precompute `entity_sets = [_entity_tokens([titles[i] for i in group]) for group in groups]`; change the merge condition to `similarity_matrix[i, j] >= context_similarity_threshold and _entities_compatible(entity_sets[i], entity_sets[j])`.
- [ ] **Step 4: run new + full grouping/e2e test files — PASS** (`pytest test/test_models_grouping.py test/test_end_to_end_grouping.py test/test_group_identifier_improved.py -v`)
- [ ] **Step 5: commit** (`fix: entity guard prevents cross-story context merges`)

### Task 3: docs, full verification, ship

- [ ] `docs/GROUPING_ALGORITHM.md`: document the guard in the two-level clustering section; `CLAUDE.md` data-flow step 3: one line.
- [ ] `make test` + `make lint` green.
- [ ] Local smoke: `newvelles --rss_file data/rss_source_short.txt`; eyeball that no top-level group mixes obviously distinct entities.
- [ ] Branch `entity-guard-clustering`, PR with the live-prod evidence, hand merge to user; after merge: `make qa-build && make qa-deploy && make qa-invoke`, then user runs `make prod-deploy`.

## Self-Review
- Repro verified before writing the test (in-isolation titles do NOT reproduce; filler corpus does). ✓
- Guard never hard-blocks entity-less groups. ✓ Labels restricted to PERSON/ORG per constraint. ✓ No caller-visible signature changes. ✓
