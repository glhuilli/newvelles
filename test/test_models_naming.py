"""Tests for newvelles.models.naming — LLM headline generation behind a provider interface."""

import json
from unittest.mock import MagicMock, patch

import pytest

from newvelles.models.naming import (PROVIDERS, _name_via_local, _postprocess, build_prompt,
                                     resolve_provider)


def _story(titles_outlets, **overrides):
    articles = [{"title": t, "outlet": o, "link": f"https://x.com/{i}",
                 "published": "2026-08-16T12:00:00Z", "domain": "x.com"}
                for i, (t, o) in enumerate(titles_outlets)]
    story = {
        "id": "st_abc123",
        "headline": max((a["title"] for a in articles), key=len),
        "headline_source": "fallback",
        "keywords": ["alaska summit"],
        "entities": ["Trump", "Putin", "Alaska"],
        "kind": "story",
        "outlet_count": len({o for _, o in titles_outlets}),
        "article_count": len(articles),
        "articles": articles,
    }
    story.update(overrides)
    return story


ALASKA_TITLES = [
    ("Trump and Putin end summit without ceasefire deal for Ukraine", "BBC"),
    ("Trump Bows to Putin's Approach on Ukraine: No Cease-Fire, Deadlines or Sanctions", "NYT"),
    ("Watch: Moment Trump and Putin meet in Alaska", "BBC"),
]


class TestBuildPrompt:
    def test_prompt_contains_rules_and_headlines(self):
        prompt = build_prompt(_story(ALASKA_TITLES))
        assert "6 to 12 words" in prompt
        assert "Reply with the sentence and nothing else." in prompt
        for title, outlet in ALASKA_TITLES:
            assert title in prompt
            assert outlet in prompt

    def test_prompt_caps_at_twelve_headlines_longest_first(self):
        many = [(f"Headline number {i} " + "word " * i, "BBC") for i in range(1, 20)]
        prompt = build_prompt(_story(many))
        listed = [line for line in prompt.splitlines() if line.strip()
                  and line.strip()[0].isdigit()]
        assert len(listed) == 12
        # longest first
        assert "Headline number 19" in listed[0]

    def test_prompt_numbering(self):
        prompt = build_prompt(_story(ALASKA_TITLES))
        assert "1. " in prompt and "3. " in prompt


class TestPostprocess:
    @pytest.mark.parametrize("raw,expected", [
        ("Trump and Putin meet in Alaska without a deal", "Trump and Putin meet in Alaska without a deal"),
        ('"Trump and Putin meet in Alaska without a deal."', "Trump and Putin meet in Alaska without a deal"),
        ("  Summit ends without ceasefire  \n", "Summit ends without ceasefire"),
        ("First line here\nSecond line ignored", "First line here"),
    ])
    def test_cleanup(self, raw, expected):
        assert _postprocess(raw) == expected

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            _postprocess("   \n ")

    def test_too_long_raises(self):
        with pytest.raises(ValueError):
            _postprocess("word " * 60)


class TestLocalProvider:
    def test_local_provider_offline_produces_phrase(self):
        headline = _name_via_local(_story(ALASKA_TITLES))
        assert isinstance(headline, str)
        assert 0 < len(headline) <= 140
        # should be grounded in the story's content
        assert any(tok in headline for tok in ("Trump", "Putin", "Alaska", "summit", "ceasefire"))

    def test_local_provider_no_trailing_period(self):
        assert not _name_via_local(_story(ALASKA_TITLES)).endswith(".")


class TestProviderRegistry:
    def test_all_four_providers_registered(self):
        assert set(PROVIDERS) == {"bedrock", "anthropic", "openai", "local"}

    def test_resolve_provider_defaults_to_local(self, monkeypatch):
        monkeypatch.delenv("NEWVELLES_NAMING_PROVIDER", raising=False)
        assert resolve_provider() == "local"

    def test_resolve_provider_from_env(self, monkeypatch):
        monkeypatch.setenv("NEWVELLES_NAMING_PROVIDER", "bedrock")
        assert resolve_provider() == "bedrock"

    def test_unknown_provider_rejected(self, monkeypatch):
        monkeypatch.setenv("NEWVELLES_NAMING_PROVIDER", "carrier-pigeon")
        with pytest.raises(KeyError):
            PROVIDERS[resolve_provider()]  # pylint: disable=pointless-statement
