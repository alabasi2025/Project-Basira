"""Developer-gate REST contract (docs/API.md): /v1/sources, /v1/rules, /v1/guard, determinism header,
OpenAPI examples for the four states. Uses the shared `client` fixture (fixture index, mock provider)."""

from __future__ import annotations

import json

from httpx import AsyncClient

from app.config import Settings
from app.messages import scan_forbidden
from app.schemas import openapi_examples

HEADER = "x-basira-determinism-hash"


async def test_sources_match_manifest_including_sha256(client: AsyncClient, test_settings: Settings) -> None:
    r = await client.get("/v1/sources")
    assert r.status_code == 200
    body = r.json()
    manifest = json.loads(test_settings.manifest_path.read_text(encoding="utf-8"))
    assert [s["id"] for s in body] == [s["id"] for s in manifest["sources"]]
    by_id = {s["id"]: s for s in body}
    for src in manifest["sources"]:
        got = by_id[src["id"]]
        assert got["sha256"] == str(src.get("sha256") or "")
        assert got["license"] == src["license"] and got["license_url"] == src["license_url"]
        assert got["version"] == str(src.get("version") or src.get("commit") or "")
        assert got["in_repo"] is False
    assert by_id["tanzil_uthmani"]["records"] > 0  # live counts from the loaded store


async def test_determinism_header_equals_body_field(client: AsyncClient) -> None:
    r = await client.post("/v1/check", json={"text": "قال تعالى: ﴿إن الله مع الصابرين﴾", "ui_lang": "ar"})
    assert r.status_code == 200
    assert HEADER in r.headers and r.headers[HEADER] == r.json()["determinism_hash"]
    assert len(r.headers[HEADER]) == 64
    r2 = await client.post("/v1/check", json={"text": "قال تعالى: ﴿إن الله مع الصابرين﴾", "ui_lang": "ar"})
    assert r2.headers[HEADER] == r.headers[HEADER]
    assert r.headers["cache-control"] == "no-store"


async def test_determinism_header_absent_on_errors(client: AsyncClient) -> None:
    r = await client.post("/v1/check", json={"text": "   "})
    assert r.status_code == 422 and HEADER not in r.headers
    assert r.json()["error"]["code"] == "invalid_input"


async def test_rules_endpoint(client: AsyncClient) -> None:
    en = (await client.get("/v1/rules")).json()
    ar = (await client.get("/v1/rules", params={"ui_lang": "ar"})).json()
    assert en["ui_lang"] == "en" and ar["ui_lang"] == "ar"
    assert en["states"] == ["found", "partial_match", "needs_review", "not_found"]
    assert (
        en["source"] == "SAFETY.md"
        and len(en["safety_sha256"]) == 64
        and en["safety_sha256"] == ar["safety_sha256"]
    )
    assert "never a verdict" in en["text"].lower() or "not a verdict" in en["text"].lower()
    assert scan_forbidden(en["text"]) == [] and scan_forbidden(ar["text"]) == []
    other = (await client.get("/v1/rules", params={"ui_lang": "fr"})).json()
    assert other["ui_lang"] == "ar"  # unknown → Arabic default, never an error


async def test_guard_endpoint_flagged(client: AsyncClient) -> None:
    r = await client.post(
        "/v1/guard",
        json={"answer": "قال تعالى: ﴿إن الله مع الصابرين﴾ وقال ﷺ: «الدين المعاملة»", "ui_lang": "ar"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["verdict"] == "flagged"
    assert body["counts"] == {
        "quotes": 2,
        "found": 1,
        "flagged": 1,
        "by_status": {"found": 1, "not_found": 1},
    }
    assert len(body["flagged_quote_ids"]) == 1
    assert body["summary_ar"] and body["summary_en"]
    assert scan_forbidden(body["summary_ar"]) == [] and scan_forbidden(body["summary_en"]) == []
    assert r.headers[HEADER] == body["determinism_hash"]


async def test_guard_endpoint_clear_and_no_quotes(client: AsyncClient) -> None:
    clear = (await client.post("/v1/guard", json={"answer": "قال تعالى: ﴿إن الله مع الصابرين﴾"})).json()
    assert clear["verdict"] == "clear" and clear["counts"]["flagged"] == 0
    none = (await client.post("/v1/guard", json={"answer": "اليوم طقس جميل", "ui_lang": "en"})).json()
    assert none["verdict"] == "no_quotes" and none["quotes"] == []


async def test_guard_endpoint_errors_use_envelope(client: AsyncClient, test_settings: Settings) -> None:
    r = await client.post("/v1/guard", json={"answer": "   "})
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_input"
    r = await client.post("/v1/guard", json={"answer": "ا" * 5001})
    assert r.status_code == 413 and r.json()["error"]["code"] == "text_too_long"
    assert str(test_settings.max_text_chars) in r.json()["error"]["message_en"]
    r = await client.post("/v1/guard", json={})
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_input"


async def test_openapi_has_real_examples_for_four_states(client: AsyncClient) -> None:
    ex = openapi_examples()
    assert set(ex) == {"found", "partial_match", "needs_review", "not_found"}
    for state, pair in ex.items():
        resp = pair["response"]
        assert resp["quotes"][0]["status"] == state
        assert len(resp["determinism_hash"]) == 64
        for q in resp["quotes"]:
            for m in q["matches"]:
                assert m["source_text"] and "…" not in m["source_text"]  # verbatim, never trimmed
    spec = (await client.get("/openapi.json")).json()
    req_schema = spec["components"]["schemas"]["CheckRequest"]
    resp_schema = spec["components"]["schemas"]["CheckResponse"]
    assert len(req_schema["examples"]) == 4 and len(resp_schema["examples"]) == 4
    assert [e["quotes"][0]["status"] for e in resp_schema["examples"]] == [
        "found",
        "partial_match",
        "needs_review",
        "not_found",
    ]
    paths = spec["paths"]
    assert {"/v1/check", "/v1/guard", "/v1/rules", "/v1/sources", "/v1/messages/{lang}", "/health"} <= set(
        paths
    )
    assert "examples" in spec["components"]["schemas"]["GuardRequest"]


async def test_openapi_examples_are_lexicon_clean() -> None:
    """Everything we author inside the examples (message keys render later; here: labels/notices) is clean."""
    for pair in openapi_examples().values():
        for q in pair["response"]["quotes"]:
            for m in q["matches"]:
                assert scan_forbidden(m["ref_label_ar"]) == [] and scan_forbidden(m["ref_label_en"]) == []
