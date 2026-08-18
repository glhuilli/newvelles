# Classification benchmark vs the Fable golden set

Golden set: 4,020 stories labeled in-session by Claude Fable 5 (stratified by
year × section × days-seen; 0 invalid lines; 6.4% "other-*", under the 8% bar).
Taxonomy v1.0 (13 majors, ~60 subs). All numbers are agreement with the golden
labels — for adjacent categories (Economy↔Markets, Crime↔Politics trials),
disagreement includes genuine boundary ambiguity, not only error.

| Route | n | Major | Sub | Sub (major correct) | Tags any-overlap | Tags Jaccard |
|---|---|---|---|---|---|---|
| A — Bedrock Haiku 4.5 (full corpus) | 3,704 | **0.823** | **0.662** | 0.793 | **0.975** | **0.495** |
| C — MiniLM embeddings + logreg, k-NN tags (held-out 25%) | 1,005 | 0.778 | 0.631 | 0.734 | 0.644 | 0.203 |
| D — qwen3:8b local (golden sample) | 2,605 | 0.427 (0.595*) | 0.262 | 0.441* | 0.654 | 0.193 |

\* case-normalized: qwen frequently lowercases major names; scored leniently it
reaches 0.595 major. Its structural reliability is the bigger cost: only
**64.8% of lines parsed** as valid JSON (batch-of-25 prompts), so real
coverage would need per-story calls plus repair logic.

## Reading

- **The quality ladder is unambiguous**: Fable (reference) → Haiku (0.82/0.66,
  tags 0.50) → embeddings (0.78/0.63, tags 0.20) → qwen3:8b (0.60*/0.26,
  35% parse loss). The local 8B model is not competitive for this taxonomy at
  batch scale; the interesting surprise is how close a 3,000-example
  embedding classifier gets to Haiku on majors — while being hopeless at
  generative tags.

- **Haiku is the production route.** Its edge over the trained classifier is
  modest on major/sub but decisive on meta tags (0.50 vs 0.20 Jaccard): tags
  are generative — a classifier can only transfer neighbors' tags, while the
  LLM writes "immigration crisis" without the words appearing in the title.
- **Route C is a credible fallback for major-level analysis** at zero marginal
  cost, trained on 3,015 examples. Its top confusions (Economy→Markets 11,
  Politics→Crime 9) mirror Haiku's, which suggests taxonomy boundary fuzziness
  rather than model weakness.
- **Full-corpus coverage: 106,050 / 114,927 (92.3%).** The last 60 Haiku shards
  hit the Bedrock daily token quota ("Too many tokens per day"). The run is
  resumable: `analysis/.venv/bin/python analysis/classify_bedrock.py --workers 8`
  after the quota resets, then `merge_labels.py` + `build_payload.py --site`.
- Haiku label normalization: 1,261 rows had a sub under the wrong major
  (sub trusted, major reassigned); 200 unknown subs fell to other-general.
