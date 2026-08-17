"""LLM headline generation behind a four-provider interface.

The story name becomes a generated neutral sentence (Claude Haiku via Amazon
Bedrock in production — IAM auth, no API key in the Lambda). The provider is
chosen by NEWVELLES_NAMING_PROVIDER and defaults to "local", a real spaCy
implementation with no network, so a fresh clone runs offline.

Naming must never fail a run: any error falls back to the story's existing
best-real-headline and is counted, so a silent outage is visible in monitoring.
"""
import json
import os
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from typing import Optional, Tuple

from newvelles.utils.text import NLP

MAX_PROMPT_HEADLINES = 12
MAX_HEADLINE_CHARS = 140
DEFAULT_MAX_CALLS = 60
DEFAULT_TIMEOUT_SECONDS = 8
DEFAULT_BEDROCK_MODEL = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
CACHE_RETENTION_DAYS = 30
RENAME_GROWTH_FACTOR = 1.5  # rename only when the article set grew >50%
NAMING_CONCURRENCY = 4
LOCAL_NAMING_CACHE_PATH = "./cache/story_names.json"

PROMPT_TEMPLATE = """You name news stories. You will get headlines that all cover the same
event, from different outlets.

Write one plain sentence naming what happened. Rules:
- 6 to 12 words, sentence case, no trailing period
- State the event, not the framing. Never adopt one outlet's angle.
- No clickbait, no questions, no colons, no "here's what"
- Use the names of people, places and organisations that appear
- If the headlines disagree about what happened, name the disputed
  fact, not one side's version

Headlines:
{headlines}

Reply with the sentence and nothing else."""


def build_prompt(story: dict) -> str:
    articles = sorted(story.get("articles", []), key=lambda a: len(a["title"]), reverse=True)
    lines = [
        f"{i}. {article['title']} ({article['outlet']})"
        for i, article in enumerate(articles[:MAX_PROMPT_HEADLINES], start=1)
    ]
    return PROMPT_TEMPLATE.format(headlines="\n".join(lines))


def _postprocess(text: str) -> str:
    """First line, stripped of quotes/whitespace/trailing period; reject junk."""
    line = text.strip().splitlines()[0].strip() if text.strip() else ""
    line = line.strip("\"'“”‘’ ").rstrip(".").strip()
    if not line:
        raise ValueError("empty headline from provider")
    if len(line) > MAX_HEADLINE_CHARS:
        raise ValueError(f"headline too long ({len(line)} chars)")
    return line


def resolve_provider() -> str:
    return os.environ.get("NEWVELLES_NAMING_PROVIDER", "local")


def _timeout_seconds() -> int:
    return int(os.environ.get("NEWVELLES_NAMING_TIMEOUT", DEFAULT_TIMEOUT_SECONDS))


def _model_id() -> str:
    return os.environ.get("NEWVELLES_NAMING_MODEL", DEFAULT_BEDROCK_MODEL)


def _name_via_bedrock(prompt: str) -> str:
    # Imported lazily so the offline/local path needs no AWS SDK setup.
    import boto3  # pylint: disable=import-outside-toplevel
    from botocore.config import Config  # pylint: disable=import-outside-toplevel

    region = os.environ.get("BEDROCK_REGION") or os.environ.get(
        "AWS_DEFAULT_REGION", "us-west-2"
    )
    client = boto3.client(
        "bedrock-runtime",
        region_name=region,
        config=Config(
            connect_timeout=3,
            read_timeout=_timeout_seconds(),
            retries={"max_attempts": 2},
        ),
    )
    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 60,
        "messages": [{"role": "user", "content": prompt}],
    }
    response = client.invoke_model(modelId=_model_id(), body=json.dumps(body))
    payload = json.loads(response["body"].read())
    return _postprocess(payload["content"][0]["text"])


def _name_via_anthropic(prompt: str) -> str:
    """Dormant escape hatch — production is all-AWS (Bedrock)."""
    import requests  # pylint: disable=import-outside-toplevel

    api_key = os.environ["ANTHROPIC_API_KEY"]
    response = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={"x-api-key": api_key, "anthropic-version": "2023-06-01",
                 "content-type": "application/json"},
        json={"model": os.environ.get("NEWVELLES_NAMING_MODEL", "claude-haiku-4-5"),
              "max_tokens": 60,
              "messages": [{"role": "user", "content": prompt}]},
        timeout=_timeout_seconds(),
    )
    response.raise_for_status()
    return _postprocess(response.json()["content"][0]["text"])


def _name_via_openai(prompt: str) -> str:
    """Dormant escape hatch — production is all-AWS (Bedrock)."""
    import requests  # pylint: disable=import-outside-toplevel

    api_key = os.environ["OPENAI_API_KEY"]
    response = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json={"model": os.environ.get("NEWVELLES_NAMING_MODEL", "gpt-5.4-nano"),
              "max_tokens": 60,
              "messages": [{"role": "user", "content": prompt}]},
        timeout=_timeout_seconds(),
    )
    response.raise_for_status()
    return _postprocess(response.json()["choices"][0]["message"]["content"])


def _name_via_local(story: dict) -> str:
    """spaCy naming with no network: the story's top entities joined with its
    most informative noun phrase. Noticeably worse than the LLM, deliberately
    real rather than a stub."""
    titles = [a["title"] for a in story.get("articles", [])]
    chunk_counts: Counter = Counter()
    for doc in NLP.pipe(titles[:MAX_PROMPT_HEADLINES]):
        for chunk in doc.noun_chunks:
            text = chunk.text.strip()
            if len(text.split()) >= 2:
                chunk_counts[text] += 1

    entities = [e for e in story.get("entities", [])][:2]
    top_chunks = []
    used_words = {w.lower() for e in entities for w in e.split()}
    for chunk, _count in chunk_counts.most_common(6):
        words = {w.lower() for w in chunk.split()}
        if words & used_words:
            continue
        top_chunks.append(chunk)
        used_words |= words
        if len(top_chunks) == 2:
            break

    parts = []
    if entities:
        parts.append(" and ".join(entities))
    parts.extend(top_chunks)
    headline = ", ".join(parts) if parts else story.get("headline", "")
    return _postprocess(headline)


PROVIDERS = {
    "bedrock": _name_via_bedrock,
    "anthropic": _name_via_anthropic,
    "openai": _name_via_openai,
    "local": _name_via_local,
}
_REMOTE_PROVIDERS = {"bedrock", "anthropic", "openai"}


def _max_calls() -> int:
    return int(os.environ.get("NEWVELLES_NAMING_MAX_CALLS", DEFAULT_MAX_CALLS))


def _needs_naming(story: dict, cache: dict) -> bool:
    cached = cache.get(story["id"])
    if cached is None:
        return True
    return story["article_count"] > cached["article_count"] * RENAME_GROWTH_FACTOR


def _call_provider(provider_name: str, story: dict) -> str:
    if provider_name == "local":
        return _name_via_local(story)
    return PROVIDERS[provider_name](build_prompt(story))


def name_stories(
    stories_data: dict,
    cache: dict,
    provider_name: Optional[str] = None,
    today: Optional[str] = None,
) -> Tuple[dict, dict, dict]:
    """Name stories via the configured provider, reusing cached names.

    Returns (stories_data, new_cache, stats). A cached story is re-named only
    when its article set has grown by more than 50% since the naming that
    produced the current headline. Failures and over-cap stories keep their
    existing best-real-headline (already set by build_stories) and are NOT
    cached, so they retry next run. Naming never raises.
    """
    provider_name = provider_name or resolve_provider()
    today = today or date.today().isoformat()
    stories = stories_data.get("stories", [])
    stats = {"llm_named": 0, "cache_hits": 0, "fallbacks": 0, "renamed": 0}

    to_name = []
    for story in stories:
        if _needs_naming(story, cache):
            to_name.append(story)
        else:
            cached = cache[story["id"]]
            story["headline"] = cached["headline"]
            story["headline_source"] = cached["headline_source"]
            stats["cache_hits"] += 1

    # cap new calls per run; real news first, in list (rank) order
    to_name.sort(key=lambda s: s.get("kind") != "story")
    budget = _max_calls()
    selected, capped = to_name[:budget], to_name[budget:]

    def _name_one(story):
        try:
            return story, _call_provider(provider_name, story)
        except Exception as error:  # noqa: BLE001 — naming must never fail a run
            print(f"⚠️ Naming failed for {story['id']} via {provider_name}: {error}")
            return story, None

    if provider_name in _REMOTE_PROVIDERS and len(selected) > 1:
        with ThreadPoolExecutor(max_workers=NAMING_CONCURRENCY) as pool:
            results = list(pool.map(lambda s: _name_one(s), selected))
    else:  # local spaCy is not thread-safe; small batches gain nothing
        results = [_name_one(story) for story in selected]

    new_cache = dict(cache)
    for story, headline in results:
        if headline is None:
            stats["fallbacks"] += 1
            continue
        source = "llm" if provider_name in _REMOTE_PROVIDERS else "fallback"
        if story["id"] in cache:
            stats["renamed"] += 1
        if source == "llm":
            stats["llm_named"] += 1
        story["headline"] = headline
        story["headline_source"] = source
        new_cache[story["id"]] = {
            "headline": headline,
            "headline_source": source,
            "article_count": story["article_count"],
            "named_at": today,
        }
    stats["fallbacks"] += len(capped)

    # prune cache entries not touched within the retention window
    horizon = (date.fromisoformat(today) - timedelta(days=CACHE_RETENTION_DAYS)).isoformat()
    new_cache = {sid: entry for sid, entry in new_cache.items()
                 if entry.get("named_at", today) >= horizon}
    return stories_data, new_cache, stats


def load_naming_cache_s3() -> dict:
    from newvelles.feed.log import _S3_BUCKET  # pylint: disable=import-outside-toplevel
    from newvelles.utils.s3 import read_json_from_s3  # pylint: disable=import-outside-toplevel
    return read_json_from_s3(_S3_BUCKET, "story_names.json") or {}


def save_naming_cache_s3(cache: dict) -> None:
    from newvelles.feed.log import _S3_BUCKET  # pylint: disable=import-outside-toplevel
    from newvelles.utils.s3 import upload_to_s3  # pylint: disable=import-outside-toplevel
    upload_to_s3(bucket_name=_S3_BUCKET, file_name="story_names.json",
                 string_byte=json.dumps(cache).encode("utf-8"))


def _local_cache_path() -> str:
    return os.environ.get("NEWVELLES_NAMING_CACHE", LOCAL_NAMING_CACHE_PATH)


def load_naming_cache_local() -> dict:
    try:
        with open(_local_cache_path(), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_naming_cache_local(cache: dict) -> None:
    path = _local_cache_path()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cache, f)
