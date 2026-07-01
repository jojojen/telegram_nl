"""Unit tests for telegram_nl.natural_language pure-function layer.

Only tests deterministic helpers — no LLM, no network.
"""
from __future__ import annotations

import pytest

from telegram_nl.natural_language import (
    _extract_opportunity_target,
    _extract_sns_schedule_minutes,
    _extract_watch_query,
    _looks_like_opportunity_remove_request,
    _looks_like_web_research_question,
    _normalize_intent,
    _normalize_keyword_values,
    _parse_kanji_number,
    _parse_price_threshold,
    _recover_lookup_fields,
    _split_keyword_phrase,
    build_telegram_natural_language_router,
    fallback_route_telegram_natural_language,
    fast_route_telegram_natural_language,
    slow_fallback_route_telegram_natural_language,
)


# ── _parse_price_threshold ────────────────────────────────────────────────────

@pytest.mark.parametrize("text,expected", [
    ("5万", 50000),
    ("50000", 50000),
    ("50,000", 50000),
    ("¥50000", 50000),
    ("30万円以下", 300000),
    ("三十万", 300000),
    ("五万", 50000),
    ("1.5万", 15000),
    ("300000日幣", 300000),
    ("低於2万", 20000),
])
def test_parse_price_threshold(text: str, expected: int) -> None:
    assert _parse_price_threshold(text) == expected


def test_parse_price_threshold_none_on_short_number() -> None:
    assert _parse_price_threshold("5") is None


def test_parse_price_threshold_none_on_empty() -> None:
    assert _parse_price_threshold("") is None


# ── _parse_kanji_number ───────────────────────────────────────────────────────

@pytest.mark.parametrize("kanji,expected", [
    ("五", 5),
    ("十", 10),
    ("三十", 30),
    ("百", 100),
    ("百二十", 120),
    ("三", 3),
])
def test_parse_kanji_number(kanji: str, expected: int) -> None:
    assert _parse_kanji_number(kanji) == expected


def test_parse_kanji_number_invalid() -> None:
    assert _parse_kanji_number("abc") is None
    assert _parse_kanji_number("") is None


# ── _extract_watch_query ─────────────────────────────────────────────────────

def test_extract_watch_query_strips_keywords_and_price() -> None:
    query = _extract_watch_query("幫我監控 ピカチュウ 5万以下")
    assert query is not None
    assert "ピカチュウ" in query
    assert "5" not in query
    assert "万" not in query


def test_extract_watch_query_returns_none_on_short_result() -> None:
    assert _extract_watch_query("監控") is None


# ── _extract_sns_schedule_minutes ────────────────────────────────────────────

@pytest.mark.parametrize("text,expected", [
    ("每 60 分鐘", 60),
    ("每720分鐘", 720),
    ("schedule 30 mins", 30),
    ("每 5 分鐘", 5),
])
def test_extract_sns_schedule_minutes_valid(text: str, expected: int) -> None:
    assert _extract_sns_schedule_minutes(text) == expected


def test_extract_sns_schedule_minutes_out_of_range() -> None:
    assert _extract_sns_schedule_minutes("每 2 分鐘") is None
    assert _extract_sns_schedule_minutes("每 2000 分鐘") is None


def test_extract_sns_schedule_minutes_no_match() -> None:
    assert _extract_sns_schedule_minutes("add twitter account @foo") is None


# ── _normalize_keyword_values ────────────────────────────────────────────────

def test_normalize_keyword_values_deduplicates() -> None:
    result = _normalize_keyword_values(["抽選", "抽選", "lottery"])
    assert result.count("抽選") == 1


def test_normalize_keyword_values_strips_quotes() -> None:
    result = _normalize_keyword_values(['"抽選"', "'lottery'"])
    assert "抽選" in result
    assert "lottery" in result


def test_normalize_keyword_values_skips_empty() -> None:
    result = _normalize_keyword_values(["", "  ", "抽選"])
    assert "" not in result
    assert "  " not in result


# ── _split_keyword_phrase ─────────────────────────────────────────────────────

def test_split_keyword_phrase_comma_separated() -> None:
    parts = _split_keyword_phrase("抽選,lottery,ガチャ")
    assert "抽選" in parts
    assert "lottery" in parts
    assert "ガチャ" in parts


def test_split_keyword_phrase_space_separated() -> None:
    parts = _split_keyword_phrase("抽選 lottery")
    assert len(parts) == 2


def test_split_keyword_phrase_empty() -> None:
    assert _split_keyword_phrase("") == []


# ── _looks_like_web_research_question ────────────────────────────────────────

def test_looks_like_web_research_question_yes() -> None:
    assert _looks_like_web_research_question("pokemon SSP 現在多少錢?") is True


def test_looks_like_web_research_question_no_subject() -> None:
    assert _looks_like_web_research_question("你好嗎?") is False


def test_looks_like_web_research_question_no_question_shape() -> None:
    assert _looks_like_web_research_question("鏈鋸人 SSP 買了") is False


# ── _looks_like_opportunity_remove_request ────────────────────────────────────

def test_looks_like_opportunity_remove_request_yes() -> None:
    assert _looks_like_opportunity_remove_request("移除 鏈鋸人 機會清單") is True
    assert _looks_like_opportunity_remove_request("I'm not interested in this anymore") is True


def test_looks_like_opportunity_remove_request_no() -> None:
    assert _looks_like_opportunity_remove_request("監控 ピカチュウ") is False


# ── _extract_opportunity_target ───────────────────────────────────────────────

def test_extract_opportunity_target_strips_noise() -> None:
    result = _extract_opportunity_target("移除 鏈鋸人 從機會清單")
    assert result is not None
    assert "鏈鋸人" in result
    assert "移除" not in result


def test_extract_opportunity_target_numeric_index() -> None:
    result = _extract_opportunity_target("remove 第3個")
    assert result == "3"


# ── _recover_lookup_fields ────────────────────────────────────────────────────

def test_recover_lookup_fields_extracts_rarity_from_name() -> None:
    name, cn, rarity, sc = _recover_lookup_fields("ピカチュウ SSP", None, None, None)
    assert rarity == "SSP"


def test_recover_lookup_fields_no_op_when_already_present() -> None:
    name, cn, rarity, sc = _recover_lookup_fields("ピカチュウ", None, "SSP", None)
    assert rarity == "SSP"
    assert name == "ピカチュウ"


# ── fallback_route_telegram_natural_language ──────────────────────────────────

def test_fallback_returns_none_on_empty() -> None:
    assert fallback_route_telegram_natural_language("") is None


def test_fallback_routes_reputation_snapshot() -> None:
    text = "https://www.mercari.com/jp/items/123456 這的出品者信用できますか"
    intent = fallback_route_telegram_natural_language(text)
    assert intent is not None
    assert intent.intent == "reputation_snapshot"
    assert intent.query_url is not None


def test_fallback_routes_opportunity_remove() -> None:
    text = "移除 鏈鋸人 從目標清單"
    intent = fallback_route_telegram_natural_language(text)
    assert intent is not None
    assert intent.intent == "opportunity_remove"


def test_fallback_routes_watch_add() -> None:
    text = "幫我監控 ピカチュウ SSP 5万以下"
    intent = fallback_route_telegram_natural_language(text)
    assert intent is not None
    assert intent.intent == "add_watch"
    assert intent.watch_price_threshold == 50000


# ── App-intent compatibility via extra_allowed_intents ───────────────────────

def test_normalize_intent_accepts_extra_allowed_create_workflow() -> None:
    payload = {"intent": "create_workflow", "workflow_description": "每天查天氣"}
    result = _normalize_intent(payload, extra_allowed_intents=frozenset({"create_workflow"}))
    assert result.intent == "create_workflow"
    assert result.workflow_description == "每天查天氣"


# ── Routing boundary characterization ────────────────────────────────────────

def test_fallback_routes_clear_filter_for_single_handle() -> None:
    result = fallback_route_telegram_natural_language("把 @example_tcg 的 filter 全部拿掉")
    assert result is not None
    assert result.intent == "sns_clear_filter"
    assert result.sns_handle == "example_tcg"


def test_fast_route_routes_clear_filter_for_single_handle() -> None:
    result = fast_route_telegram_natural_language("把 @example_tcg 的 filter 全部拿掉")
    assert result is not None
    assert result.intent == "sns_clear_filter"
    assert result.sns_handle == "example_tcg"


def test_slow_fallback_does_not_route_clear_filter_fast_path_case() -> None:
    result = slow_fallback_route_telegram_natural_language("把 @example_tcg 的 filter 全部拿掉")
    assert result is None


def test_fallback_delete_phrase_still_routes_to_sns_delete() -> None:
    result = fallback_route_telegram_natural_language("刪除追蹤 @example_news")
    assert result is not None
    assert result.intent == "sns_delete"
    assert result.sns_handle == "example_news"


def test_fallback_routes_schedule_update_to_sns_add_account_with_minutes() -> None:
    result = fallback_route_telegram_natural_language("把 @example_sched 的追蹤排程改成每 720分鐘")
    assert result is not None
    assert result.intent == "sns_add_account"
    assert result.sns_handle == "example_sched"
    assert result.sns_schedule_minutes == 720


def test_fallback_routes_bulk_schedule_update_with_explicit_plural() -> None:
    result = fallback_route_telegram_natural_language(
        "所有 yugioh 帳號排程改成每 60 分鐘"
    )
    assert result is not None
    assert result.intent == "sns_bulk_update_schedule"
    assert result.bulk_target_domain == "yugioh"
    assert result.sns_schedule_minutes == 60


def test_fallback_returns_none_for_bulk_schedule_without_explicit_plural() -> None:
    result = fallback_route_telegram_natural_language(
        "把 sns 監控規則裡 domain 有 tcg 的帳號 追蹤頻率都改成每 720 分鐘"
    )
    assert result is None or result.intent != "sns_bulk_update_schedule"


def test_fallback_requires_filter_hint_for_clear_filter() -> None:
    result = fallback_route_telegram_natural_language("拿掉 @example_bot")
    assert result is None or result.intent != "sns_clear_filter"


def test_fallback_returns_none_for_bare_marketplace_url() -> None:
    result = fallback_route_telegram_natural_language("https://jp.mercari.com/shops/product/abc123")
    assert result is None


def test_fallback_returns_none_for_unrelated_message() -> None:
    result = fallback_route_telegram_natural_language("明天天氣如何")
    assert result is None


def test_slow_fallback_no_longer_routes_openclaw_app_intents() -> None:
    result = slow_fallback_route_telegram_natural_language("建立 workflow：每天查天氣並念出來")
    assert result is None


def test_normalize_intent_accepts_clear_filter_payload() -> None:
    payload = {"intent": "sns_clear_filter", "sns_handle": "example_tcg"}
    result = _normalize_intent(payload)
    assert result.intent == "sns_clear_filter"
    assert result.sns_handle == "example_tcg"


def test_normalize_intent_rejects_out_of_range_schedule_in_payload() -> None:
    for bad in (4, 1500, "not a number", None):
        payload = {
            "intent": "sns_add_account",
            "sns_handle": "x",
            "sns_schedule_minutes": bad,
        }
        result = _normalize_intent(payload)
        assert result.sns_schedule_minutes is None


def test_build_router_accepts_extra_allowed_intents_param_for_compat() -> None:
    router = build_telegram_natural_language_router(
        endpoint="http://localhost:11434",
        model="gemma3:4b",
        extra_allowed_intents=frozenset({"my_custom_intent"}),
    )
    assert router is not None
    assert "my_custom_intent" in router._extra_allowed_intents
