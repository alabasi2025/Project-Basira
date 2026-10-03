"""BYOK — bring-your-own-key model selection (E-051).

The product is deterministic; the model only *proposes spans* (extraction), *reads images* (OCR) and
*picks an approved English translation* (E-048). None of those paths lets model text reach the user.
So letting a visitor plug in their own Genspark proxy key is safe by construction, provided:

* the key is **never stored** on the server — it travels in a request header and dies with the request
  (ADR-004: we store nothing; logs carry method/path/status only, never headers);
* the key never appears in any response, error envelope or log line;
* the model id is validated against the curated catalog below (a visitor cannot route us to an arbitrary
  model string) — the catalog is what the UI shows, with numbers **measured on 2026-10-03** by
  ``scripts/bench_models.py`` against this repository's real extraction prompt and a real OCR image;
* a bad key degrades exactly like any provider failure: rules-only extraction, ``extraction_degraded=true``,
  OCR → honest empty result. Nothing invents.

Headers (CORS-allowed, see ``main.py``)::

    X-Basira-LLM-Key:    gsk-…            (required for BYOK; absent → server defaults)
    X-Basira-LLM-Model:  <catalog id>     (optional; default = catalog default)
    X-Basira-LLM-Base:   <url>            (optional; must be an https URL from ALLOWED_BASES)
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Literal

import httpx

from app.english_gate import EnglishPicker
from app.providers.base import LLMClient, ProviderError, VisionClient

log = logging.getLogger(__name__)

GENSPARK_BASE = "https://www.genspark.ai/api/llm_proxy/v1"
ALLOWED_BASES: frozenset[str] = frozenset({GENSPARK_BASE, "https://api.openai.com/v1"})

Tier = Literal["flagship", "balanced", "fast"]


@dataclass(frozen=True, slots=True)
class ModelInfo:
    """One catalog row. Numbers are measured, not vendor claims (see ``docs/MODELS.md``)."""

    id: str
    label: str
    vendor: str
    tier: Tier
    cost_x: float  # Genspark relative credit multiplier as displayed in the proxy UI (2026-10-03)
    extract_exact: int  # /6 extraction cases exact-span
    extract_p50_ms: int
    ocr_ok: bool  # read docs/manual-test/images/01_ayah_typo.png faithfully (3 lines, no additions)
    ocr_ms: int | None
    vision: bool
    note_ar: str
    note_en: str


# Measured 2026-10-03 on the Genspark proxy with the owner's key; 6 extraction cases (4 marked Arabic
# quotes incl. a foreign token inside an ayah, 1 unmarked saying, 1 plain text, 1 English quote).
# "exact" = produced exactly the gold span list; every model returned only verbatim substrings.
CATALOG: tuple[ModelInfo, ...] = (
    ModelInfo(
        "gpt-5.4-mini",
        "GPT-5.4 mini",
        "OpenAI",
        "fast",
        0.3,
        6,
        1220,
        True,
        1343,
        True,
        "الأدق والأسرع في قياسنا: 6/6 مواضع مطابقة، ~1.2 ث، قراءة الصورة مطابقة وبأقل تكلفة. الخيار الافتراضي.",
        "Best measured accuracy and speed: 6/6 exact spans, ~1.2 s, faithful OCR, lowest cost. Default.",
    ),
    ModelInfo(
        "glm-5p3-flash-low",
        "GLM-5.3 Flash (low)",
        "Z.ai",
        "fast",
        0.15,
        6,
        1517,
        True,
        1610,
        True,
        "6/6 مواضع، ~1.5 ث، أرخص خيار مقيس. قراءة الصورة مطابقة مع خطأ إملائي واحد في كلمة خارج الاقتباس.",
        "6/6 spans, ~1.5 s, cheapest measured option. OCR faithful with one spelling slip outside the quote.",
    ),
    ModelInfo(
        "gpt-6-luna",
        "GPT-6 Luna",
        "OpenAI",
        "fast",
        0.1,
        6,
        2690,
        True,
        4619,
        True,
        "6/6 مواضع، ~2.7 ث. قراءة الصورة مطابقة لكنها أبطأ (~4.6 ث).",
        "6/6 spans, ~2.7 s. Faithful OCR but slower (~4.6 s).",
    ),
    ModelInfo(
        "claude-sonnet-5-5",
        "Claude Sonnet 5.5",
        "Anthropic",
        "balanced",
        2.0,
        5,
        3016,
        True,
        1676,
        True,
        "5/6 (تجاهل قولًا غير مُعلَّم — وهذا ما يفعله المحرك أصلًا)، ~3 ث، أسرع قراءة صورة بين النماذج الكبيرة.",
        "5/6 (skipped an unmarked saying — the rule engine covers it), ~3 s, fastest OCR among large models.",
    ),
    ModelInfo(
        "gpt-6-sol",
        "GPT-6 Sol",
        "OpenAI",
        "balanced",
        2.0,
        5,
        2069,
        True,
        2662,
        True,
        "5/6، أسرع النماذج الكبيرة في الاستخراج (~2.1 ث)، قراءة صورة مطابقة.",
        "5/6, fastest large model on extraction (~2.1 s), faithful OCR.",
    ),
    ModelInfo(
        "claude-opus-5-5",
        "Claude Opus 5.5",
        "Anthropic",
        "flagship",
        4.0,
        4,
        4530,
        True,
        2545,
        True,
        "أقوى نموذج عام لكنه ليس الأفضل هنا: 4/6 ورفض مرة الإجابة بصيغة JSON (المحرك يُكمل بالقواعد). ~4.5 ث. قراءة الصورة مطابقة.",
        "Strongest general model but not the best here: 4/6 and once refused the JSON format (rules take over). ~4.5 s. Faithful OCR.",
    ),
    ModelInfo(
        "claude-fable-5-1",
        "Claude Fable 5.1",
        "Anthropic",
        "flagship",
        10.0,
        5,
        3833,
        True,
        None,
        True,
        "5/6، ~3.8 ث لكن بتذبذب يصل إلى 11 ث. الأغلى (10×). لا مبرر لاستخدامه هنا.",
        "5/6, ~3.8 s with spikes to 11 s. Most expensive (10×). Not justified for this task.",
    ),
    ModelInfo(
        "gpt-5.5",
        "GPT-5.5",
        "OpenAI",
        "flagship",
        5.0,
        4,
        7486,
        True,
        None,
        True,
        "4/6 وأبطأ النماذج الكبيرة (~7.5 ث)؛ أدرج عبارة العزو «رواه البخاري» كاقتباس.",
        "4/6 and the slowest flagship (~7.5 s); listed the attribution «رواه البخاري» as a quote.",
    ),
    ModelInfo(
        "gpt-5.4",
        "GPT-5.4",
        "OpenAI",
        "balanced",
        3.0,
        4,
        4124,
        True,
        6715,
        True,
        "4/6، ~4.1 ث مع ذروة 8 ث. كان النموذج المرجعي في E-030؛ تجاوزته النماذج الأخف.",
        "4/6, ~4.1 s with an 8 s spike. Was the E-030 reference; lighter models now beat it.",
    ),
    ModelInfo(
        "gpt-6-astra",
        "GPT-6 Astra",
        "OpenAI",
        "flagship",
        10.0,
        4,
        3022,
        True,
        None,
        True,
        "4/6، ~3 ث. 10× التكلفة بلا مكسب مقيس على هذه المهمة.",
        "4/6, ~3 s. 10× cost with no measured gain on this task.",
    ),
)
CATALOG_IDS: frozenset[str] = frozenset(m.id for m in CATALOG)
DEFAULT_MODEL = "gpt-5.4-mini"

_KEY_RE = re.compile(r"^[A-Za-z0-9_\-\.]{16,512}$")


class ByokError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class ByokChoice:
    api_key: str
    model: str
    base_url: str

    def __repr__(self) -> str:  # never leak the key through repr/logging
        return f"ByokChoice(model={self.model!r}, base_url={self.base_url!r}, api_key='***')"


def parse_headers(headers: Any) -> ByokChoice | None:
    """``None`` when the request carries no key (server defaults apply). Raises ``ByokError`` on a
    malformed key, an unknown model id or a base URL outside the allow-list."""
    key = (headers.get("x-basira-llm-key") or "").strip()
    if not key:
        return None
    if not _KEY_RE.match(key):
        raise ByokError("byok_key_invalid")
    model = (headers.get("x-basira-llm-model") or DEFAULT_MODEL).strip()
    if model not in CATALOG_IDS:
        raise ByokError("byok_model_unknown")
    base = (headers.get("x-basira-llm-base") or GENSPARK_BASE).strip().rstrip("/")
    if base not in ALLOWED_BASES:
        raise ByokError("byok_base_not_allowed")
    return ByokChoice(key, model, base)


def catalog_payload() -> list[dict[str, Any]]:
    return [
        {
            "id": m.id,
            "label": m.label,
            "vendor": m.vendor,
            "tier": m.tier,
            "cost_x": m.cost_x,
            "extract_exact": m.extract_exact,
            "extract_total": 6,
            "extract_p50_ms": m.extract_p50_ms,
            "ocr_ok": m.ocr_ok,
            "ocr_ms": m.ocr_ms,
            "vision": m.vision,
            "note_ar": m.note_ar,
            "note_en": m.note_en,
            "default": m.id == DEFAULT_MODEL,
        }
        for m in CATALOG
    ]


def build_providers(choice: ByokChoice) -> tuple[LLMClient, VisionClient, EnglishPicker]:
    from app.providers.openai_compat import (  # noqa: PLC0415
        OpenAICompatLLM,
        OpenAICompatPicker,
        OpenAICompatVision,
    )

    llm = OpenAICompatLLM(base_url=choice.base_url, api_key=choice.api_key, model=choice.model)
    vision = OpenAICompatVision(base_url=choice.base_url, api_key=choice.api_key, model=choice.model)
    picker = OpenAICompatPicker(base_url=choice.base_url, api_key=choice.api_key, model=choice.model)
    return llm, vision, picker


async def verify_key(choice: ByokChoice, timeout_s: float = 15.0) -> dict[str, Any]:
    """One tiny completion to prove the key+model pair works. Returns ``{ok, model, latency_ms}`` or
    ``{ok: False, reason}`` — the reason is a class (``auth``, ``model``, ``transport``), never the body."""
    import time  # noqa: PLC0415

    body = {
        "model": choice.model,
        "temperature": 0,
        "max_tokens": 5,
        "messages": [{"role": "user", "content": "Reply with the single word: ok"}],
    }
    t0 = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            r = await client.post(
                choice.base_url + "/chat/completions",
                headers={"Authorization": f"Bearer {choice.api_key}", "Content-Type": "application/json"},
                json=body,
            )
    except httpx.HTTPError as exc:
        return {"ok": False, "reason": "transport", "detail": exc.__class__.__name__}
    ms = int((time.perf_counter() - t0) * 1000)
    if r.status_code in (401, 403):
        return {"ok": False, "reason": "auth", "latency_ms": ms}
    if r.status_code == 400:
        return {"ok": False, "reason": "model", "latency_ms": ms}
    if r.status_code != 200:
        return {"ok": False, "reason": "transport", "detail": f"http {r.status_code}", "latency_ms": ms}
    try:
        content = r.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError, ValueError):
        return {"ok": False, "reason": "transport", "detail": "malformed", "latency_ms": ms}
    if not isinstance(content, str):
        raise ProviderError("non-string content")
    return {"ok": True, "model": choice.model, "latency_ms": ms}
