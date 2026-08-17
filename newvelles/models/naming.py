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
