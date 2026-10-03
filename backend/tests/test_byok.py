"""BYOK (E-051): a visitor's own model key is used for one request and never stored, echoed or logged;
the deterministic core is unaffected by the model choice; a bad key degrades honestly."""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx
import pytest
from httpx import AsyncClient

import app.main as main_mod
from app import byok
from app.byok import CATALOG, CATALOG_IDS, DEFAULT_MODEL, ByokChoice, ByokError, parse_headers
from app.messages import scan_forbidden

# ----------------------------------------------------------------------------- header parsing


def test_no_key_means_server_defaults() -> None:
    assert parse_headers({}) is None
    assert parse_headers({"x-basira-llm-model": "gpt-5.4-mini"}) is None


def test_default_model_is_in_catalog_and_fast() -> None:
    assert DEFAULT_MODEL in CATALOG_IDS
    best = max(CATALOG, key=lambda m: (m.extract_exact, -m.extract_p50_ms))
    assert best.id == DEFAULT_MODEL, "the default must be the best measured model"


@pytest.mark.parametrize(
    ("headers", "code"),
    [
        ({"x-basira-llm-key": "short"}, "byok_key_invalid"),
        ({"x-basira-llm-key": "gsk-" + "a" * 20 + " space"}, "byok_key_invalid"),
        ({"x-basira-llm-key": "gsk-" + "a" * 40, "x-basira-llm-model": "gpt-4o"}, "byok_model_unknown"),
        (
            {"x-basira-llm-key": "gsk-" + "a" * 40, "x-basira-llm-base": "http://evil.example/v1"},
            "byok_base_not_allowed",
        ),
    ],
)
def test_rejects_bad_headers(headers: dict[str, str], code: str) -> None:
    with pytest.raises(ByokError) as ei:
        parse_headers(headers)
    assert ei.value.code == code


def test_choice_repr_never_leaks_key() -> None:
    c = ByokChoice("gsk-SECRET" + "x" * 30, DEFAULT_MODEL, byok.GENSPARK_BASE)
    assert "SECRET" not in repr(c) and "SECRET" not in str(c)


def test_catalog_notes_pass_forbidden_scan() -> None:
    for m in CATALOG:
        assert scan_forbidden(m.note_ar) == [], m.id
        assert scan_forbidden(m.note_en) == [], m.id


# ----------------------------------------------------------------------------- HTTP surface


async def test_models_catalog_endpoint(client: AsyncClient) -> None:
    r = await client.get("/v1/models")
    assert r.status_code == 200
    body = r.json()
    assert body["default"] == DEFAULT_MODEL
    ids = [m["id"] for m in body["models"]]
    assert ids[0] == DEFAULT_MODEL and len(ids) == len(CATALOG)
    for m in body["models"]:
        assert m["extract_total"] == 6 and 0 <= m["extract_exact"] <= 6
        assert set(m) >= {
            "label",
            "vendor",
            "tier",
            "cost_x",
            "extract_p50_ms",
            "ocr_ok",
            "note_ar",
            "note_en",
        }


async def test_check_with_bad_key_degrades_not_errors(
    client: AsyncClient, caplog: pytest.LogCaptureFixture
) -> None:
    """A wrong key must never break the deterministic answer or leak: rules-only + degraded flag."""
    secret = "gsk-" + "WRONGKEY" * 6

    original = byok.build_providers

    def fake_build(choice: ByokChoice) -> Any:
        llm, vision, picker = original(choice)
        llm._url = "http://127.0.0.1:9/chat/completions"  # unroutable → transport error
        return llm, vision, picker

    main_mod.build_providers = fake_build  # type: ignore[attr-defined]
    try:
        with caplog.at_level(logging.DEBUG):
            r = await client.post(
                "/v1/check",
                json={"text": "قال تعالى: ﴿إن الله مع الصابرين﴾", "ui_lang": "ar"},
                headers={"X-Basira-LLM-Key": secret, "X-Basira-LLM-Model": DEFAULT_MODEL},
            )
    finally:
        main_mod.build_providers = original  # type: ignore[attr-defined]
    assert r.status_code == 200
    body = r.json()
    assert body["extraction_degraded"] is True
    assert body["extraction_provider"] == f"openai-compatible:{DEFAULT_MODEL}"
    assert body["quotes"] and body["quotes"][0]["status"] == "found"  # rules carried the answer
    dumped = json.dumps(body) + caplog.text + str(dict(r.headers))
    assert "WRONGKEY" not in dumped


async def test_check_same_verdict_and_hash_with_or_without_byok(client: AsyncClient) -> None:
    """The model only proposes spans; a marked quote is found by rules → identical determinism hash."""
    text = "قال تعالى: ﴿إن الله مع الصابرين﴾"
    a = await client.post("/v1/check", json={"text": text, "ui_lang": "ar"})
    original = byok.build_providers

    def fake_build(choice: ByokChoice) -> Any:
        llm, vision, picker = original(choice)
        llm._url = "http://127.0.0.1:9/chat/completions"
        return llm, vision, picker

    main_mod.build_providers = fake_build  # type: ignore[attr-defined]
    try:
        b = await client.post(
            "/v1/check", json={"text": text, "ui_lang": "ar"}, headers={"X-Basira-LLM-Key": "gsk-" + "k" * 40}
        )
    finally:
        main_mod.build_providers = original  # type: ignore[attr-defined]
    assert a.json()["determinism_hash"] == b.json()["determinism_hash"]
    assert [q["status"] for q in a.json()["quotes"]] == [q["status"] for q in b.json()["quotes"]]


async def test_check_rejects_unknown_model_with_envelope(client: AsyncClient) -> None:
    r = await client.post(
        "/v1/check",
        json={"text": "نص", "ui_lang": "ar"},
        headers={"X-Basira-LLM-Key": "gsk-" + "k" * 40, "X-Basira-LLM-Model": "gpt-99"},
    )
    assert r.status_code == 400
    err = r.json()["error"]
    assert err["code"] == "byok_model_unknown" and err["message_ar"] and err["message_en"]


async def test_verify_requires_key(client: AsyncClient) -> None:
    r = await client.post("/v1/models/verify")
    assert r.status_code == 400 and r.json()["error"]["code"] == "byok_key_invalid"


async def test_verify_key_classifies_without_echo(monkeypatch: pytest.MonkeyPatch) -> None:
    secret = "gsk-" + "S3CRET" * 8
    choice = ByokChoice(secret, DEFAULT_MODEL, byok.GENSPARK_BASE)

    class _Resp:
        def __init__(self, status: int, payload: Any) -> None:
            self.status_code = status
            self._p = payload

        def json(self) -> Any:
            return self._p

    class _Client:
        def __init__(self, status: int, payload: Any) -> None:
            self._r = _Resp(status, payload)

        async def __aenter__(self) -> _Client:
            return self

        async def __aexit__(self, *a: Any) -> None:
            return None

        async def post(self, *a: Any, **k: Any) -> _Resp:
            return self._r

    for status, payload, expect in [
        (401, {}, "auth"),
        (400, {}, "model"),
        (500, {}, "transport"),
        (200, {"choices": [{"message": {"content": "ok"}}]}, None),
    ]:
        monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **k: _Client(status, payload))  # noqa: B023
        out = await byok.verify_key(choice)
        if expect is None:
            assert out["ok"] is True and out["model"] == DEFAULT_MODEL
        else:
            assert out["ok"] is False and out["reason"] == expect
        assert "S3CRET" not in json.dumps(out)
