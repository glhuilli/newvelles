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
        # incoherent-cluster instruction: name the dominant event, never comment on the input
        assert "the single item with the most headlines" in prompt
        assert "Never describe or evaluate the" in prompt
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

    @pytest.mark.parametrize("meta", [
        "These headlines appear to cover different events and cannot be combined",
        "These headlines are primarily product recommendations and shopping guides",
        "The headlines describe unrelated stories",
        "I cannot name this story as one event",
        "Unable to determine a single event from the provided headlines",
        "Articles covered different technology topics without a common event",
        "Coverage spans various topics with no single event",
    ])
    def test_meta_commentary_rejected(self, meta):
        """A refusal to name the cluster must fall back to a real headline,
        never reach the site as a 'headline'. Observed live in the first QA run."""
        with pytest.raises(ValueError):
            _postprocess(meta)

    def test_legitimate_headline_mentioning_news_is_kept(self):
        assert _postprocess("Newspaper industry faces steep advertising decline") \
            == "Newspaper industry faces steep advertising decline"

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


class TestBedrockProvider:
    def _bedrock_response(self, text):
        body = MagicMock()
        body.read.return_value = json.dumps(
            {"content": [{"type": "text", "text": text}]}).encode()
        return {"body": body}

    @patch("boto3.client")
    def test_invokes_inference_profile_with_correct_body(self, mock_client, monkeypatch):
        monkeypatch.delenv("NEWVELLES_NAMING_MODEL", raising=False)
        from newvelles.models.naming import _name_via_bedrock
        mock_client.return_value.invoke_model.return_value = self._bedrock_response(
            "Trump and Putin meet in Alaska without a ceasefire deal.")

        result = _name_via_bedrock("PROMPT")

        assert result == "Trump and Putin meet in Alaska without a ceasefire deal"
        call = mock_client.return_value.invoke_model.call_args
        assert call.kwargs["modelId"] == "us.anthropic.claude-haiku-4-5-20251001-v1:0"
        body = json.loads(call.kwargs["body"])
        assert body["anthropic_version"] == "bedrock-2023-05-31"
        assert body["messages"] == [{"role": "user", "content": "PROMPT"}]
        # timeout/retry config at the network boundary
        config = mock_client.call_args.kwargs["config"]
        assert config.read_timeout == 8
        assert config.retries == {"max_attempts": 2}

    @patch("boto3.client")
    def test_model_and_timeout_env_overrides(self, mock_client, monkeypatch):
        monkeypatch.setenv("NEWVELLES_NAMING_MODEL", "us.anthropic.other-model-v1:0")
        monkeypatch.setenv("NEWVELLES_NAMING_TIMEOUT", "3")
        from newvelles.models.naming import _name_via_bedrock
        mock_client.return_value.invoke_model.return_value = self._bedrock_response("A headline")

        _name_via_bedrock("PROMPT")

        assert mock_client.return_value.invoke_model.call_args.kwargs["modelId"] == \
            "us.anthropic.other-model-v1:0"
        assert mock_client.call_args.kwargs["config"].read_timeout == 3

    @patch("boto3.client")
    def test_provider_error_propagates(self, mock_client):
        from newvelles.models.naming import _name_via_bedrock
        mock_client.return_value.invoke_model.side_effect = RuntimeError("throttled")
        with pytest.raises(RuntimeError):
            _name_via_bedrock("PROMPT")


class TestDormantProviders:
    def test_anthropic_requires_key(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        from newvelles.models.naming import _name_via_anthropic
        with pytest.raises(KeyError):
            _name_via_anthropic("PROMPT")

    def test_openai_requires_key(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        from newvelles.models.naming import _name_via_openai
        with pytest.raises(KeyError):
            _name_via_openai("PROMPT")

    @patch("requests.post")
    def test_anthropic_call_shape(self, mock_post, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        from newvelles.models.naming import _name_via_anthropic
        mock_post.return_value.json.return_value = {"content": [{"text": "A headline"}]}
        assert _name_via_anthropic("PROMPT") == "A headline"
        assert mock_post.call_args.kwargs["headers"]["x-api-key"] == "sk-test"


class TestNameStories:
    def _doc(self, stories):
        return {"version": "0.3.0", "generated": "2026-08-16T12:00:00",
                "story_count": len(stories), "stories": stories}

    def _fake_provider(self, calls):
        def provider(prompt):
            calls.append(prompt)
            return f"Generated headline number {len(calls)}"
        return provider

    def test_new_story_named_and_cached(self):
        from newvelles.models.naming import name_stories
        calls = []
        with patch.dict(PROVIDERS, {"bedrock": self._fake_provider(calls)}):
            doc, cache, stats = name_stories(self._doc([_story(ALASKA_TITLES)]), {},
                                             provider_name="bedrock")
        assert len(calls) == 1
        story = doc["stories"][0]
        assert story["headline"] == "Generated headline number 1"
        assert story["headline_source"] == "llm"
        assert cache["st_abc123"]["headline"] == "Generated headline number 1"
        assert cache["st_abc123"]["article_count"] == 3
        assert stats == {"llm_named": 1, "local_named": 0, "cache_hits": 0, "fallbacks": 0, "renamed": 0}

    def test_cache_hit_prevents_second_call(self):
        from newvelles.models.naming import name_stories
        calls = []
        cache = {"st_abc123": {"headline": "Cached headline", "headline_source": "llm",
                               "article_count": 3, "named_at": "2026-08-16"}}
        with patch.dict(PROVIDERS, {"bedrock": self._fake_provider(calls)}):
            doc, _, stats = name_stories(self._doc([_story(ALASKA_TITLES)]), cache,
                                         provider_name="bedrock")
        assert calls == []
        assert doc["stories"][0]["headline"] == "Cached headline"
        assert doc["stories"][0]["headline_source"] == "llm"
        assert stats["cache_hits"] == 1

    def test_rename_only_when_grown_more_than_fifty_percent(self):
        from newvelles.models.naming import name_stories
        # cached at 4 articles; story now has 6 (= exactly 1.5x) -> keep
        cache = {"st_abc123": {"headline": "Cached headline", "headline_source": "llm",
                               "article_count": 4, "named_at": "2026-08-16"}}
        six = _story(ALASKA_TITLES + [("A", "X"), ("B", "Y"), ("C", "Z")])
        calls = []
        with patch.dict(PROVIDERS, {"bedrock": self._fake_provider(calls)}):
            doc, _, stats = name_stories(self._doc([six]), dict(cache),
                                         provider_name="bedrock")
        assert calls == [] and doc["stories"][0]["headline"] == "Cached headline"

        # story now has 7 articles (> 1.5 x 4) -> rename
        seven = _story(ALASKA_TITLES + [("A", "X"), ("B", "Y"), ("C", "Z"), ("D", "W")])
        with patch.dict(PROVIDERS, {"bedrock": self._fake_provider(calls)}):
            doc, new_cache, stats = name_stories(self._doc([seven]), dict(cache),
                                                 provider_name="bedrock")
        assert len(calls) == 1
        assert doc["stories"][0]["headline"] == "Generated headline number 1"
        assert stats["renamed"] == 1
        assert new_cache["st_abc123"]["article_count"] == 7

    def test_provider_failure_keeps_fallback_and_does_not_cache(self):
        from newvelles.models.naming import name_stories

        def exploding(prompt):
            raise RuntimeError("bedrock down")

        story = _story(ALASKA_TITLES)
        original = story["headline"]
        with patch.dict(PROVIDERS, {"bedrock": exploding}):
            doc, cache, stats = name_stories(self._doc([story]), {}, provider_name="bedrock")
        assert doc["stories"][0]["headline"] == original
        assert doc["stories"][0]["headline_source"] == "fallback"
        assert cache == {}
        assert stats["fallbacks"] == 1

    def test_cap_prioritizes_story_kind_and_skips_rest(self, monkeypatch):
        from newvelles.models.naming import name_stories
        monkeypatch.setenv("NEWVELLES_NAMING_MAX_CALLS", "2")
        calls = []
        deal = _story([("This Monitor Is $120 Off", "Lifehacker")], id="st_deal01", kind="deal")
        s1 = _story(ALASKA_TITLES, id="st_news01")
        s2 = _story(ALASKA_TITLES, id="st_news02")
        with patch.dict(PROVIDERS, {"bedrock": self._fake_provider(calls)}):
            doc, cache, stats = name_stories(self._doc([deal, s1, s2]), {},
                                             provider_name="bedrock")
        assert len(calls) == 2
        by_id = {s["id"]: s for s in doc["stories"]}
        assert by_id["st_news01"]["headline_source"] == "llm"
        assert by_id["st_news02"]["headline_source"] == "llm"
        assert by_id["st_deal01"]["headline_source"] == "fallback"  # capped out
        assert "st_deal01" not in cache  # retried next run
        assert stats["fallbacks"] == 1

    def test_local_provider_marks_fallback_source(self):
        from newvelles.models.naming import name_stories
        doc, cache, stats = name_stories(self._doc([_story(ALASKA_TITLES)]), {},
                                         provider_name="local")
        assert doc["stories"][0]["headline_source"] == "fallback"
        assert stats["llm_named"] == 0
        assert cache["st_abc123"]["headline_source"] == "fallback"

    def test_cache_prunes_old_entries(self):
        from newvelles.models.naming import name_stories
        stale = {"st_old999": {"headline": "Old", "headline_source": "llm",
                               "article_count": 2, "named_at": "2026-06-01"}}
        with patch.dict(PROVIDERS, {"bedrock": self._fake_provider([])}):
            _, cache, _ = name_stories(self._doc([]), stale, provider_name="bedrock",
                                       today="2026-08-16")
        assert "st_old999" not in cache


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
