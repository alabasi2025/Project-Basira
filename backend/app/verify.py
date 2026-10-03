"""Post-validator (BUILD_SPEC §3.6, SAFETY §2.1) — runs on the COMPLETE response before it is sent.

Six checks. V1–V5 failures downgrade the affected quote to ``needs_review`` with
``review_reason="validator_reject"`` and empty its matches; a V6 failure downgrades to
``needs_review`` with ``review_reason="validator_unproven"`` (matches kept, so the user still sees
the closest record). Both increment ``validator_rejections``. Nothing is logged about the user text.

  V1  every ``matches[].source_text`` is byte-equal to the corpus record's display field
      for the same (corpus, ref) — no religious text may reach the user unless it is the
      verbatim corpus field; in ``HADEETHENC_MODE=link`` a HadeethEnc match must carry an
      EMPTY body (text is linked, never embedded — owner Q2);
  V2  every ``ref`` exists in the store;
  V3  ``grade`` (if present) equals the HadeethEnc record's own ``grade``/``takhrij``/``link``
      and the match corpus is ``hadeethenc``;
  V4  forbidden lexicon scan over every string WE produce (message keys are looked up in both
      languages and scanned; ``ref_label_*``, notice keys, diff kinds) — literal corpus fields,
      ``quoted_text`` (user's own text) and the grade line are exempt;
  V5  ``disclaimer_key`` and ``transparency_key`` present and resolvable;
  V6  (B04, I17) **independent proof of every ``found``**: the strict tokens of ``quoted_text`` —
      re-derived here with ``normalize.strict_tokens`` — must occur as one contiguous window inside
      the strict token stream of the first match's record (Quran: inside the surah stream starting
      at that ayah, so a quote spanning consecutive ayat is covered; either rasm per word, E-024;
      the basmala offset is honoured). The proof uses only the Store's token streams, never the
      matcher's hits, scores or carriers. A quote of a vocalised text is compared on letters only
      (tashkeel is V-independent and handled by I14 upstream).

The validator is deliberately independent from the pipeline: it re-derives truth from the
Store, not from any intermediate object.
"""

from __future__ import annotations

from pathlib import Path

from app.messages import load_messages, scan_forbidden
from app.normalize import strict_tokens
from app.schemas import CheckResponse, Match, QuoteResult
from app.store import Record, Store

MAX_PROOF_SPAN_TOKENS = 4096  # a Quran surah stream window large enough for any real quote


def _lookup(store: Store, m: Match) -> Record | None:
    r = m.ref
    try:
        if m.corpus == "tanzil":
            return store.lookup("tanzil", surah=int(r["surah"]), ayah=int(r["ayah"]))
        if m.corpus == "ohd":
            return store.lookup("ohd", book=str(r["book"]), num=int(r["num"]))
        return store.lookup("hadeethenc", id=int(r["id"]))
    except (KeyError, TypeError, ValueError):
        return None


def _match_ok(store: Store, m: Match, *, hadeethenc_link: bool) -> bool:
    rec = _lookup(store, m)
    if rec is None:  # V2
        return False
    if rec.corpus == "hadeethenc" and hadeethenc_link:
        # link mode (Q2): the full text is NOT embedded; only an empty body is acceptable
        if m.source_text != "":
            return False
    elif m.source_text != rec.display:  # V1 (byte-exact; display is the verbatim corpus field)
        return False
    if m.grade is not None:  # V3
        if rec.corpus != "hadeethenc":
            return False
        if m.grade.text != rec.grade or m.grade.takhrij != rec.takhrij or m.grade.url != rec.link:
            return False
    return True


def _our_strings(q: QuoteResult, messages_dir: Path) -> list[str]:
    out: list[str] = []
    for lang in ("ar", "en"):
        msgs = load_messages(messages_dir, lang)
        if msgs.has("status", q.message_key):
            out.append(msgs.get("status", q.message_key))
        for k in q.notice_keys:
            if k == "grade_line":
                continue  # attributed quotation of the corpus grade (exempt by design)
            if msgs.has("notice", k):
                out.append(msgs.get("notice", k))
    for m in q.matches:
        out.append(m.ref_label_ar)
        out.append(m.ref_label_en)
        out.extend(m.diff_kinds)
    return out


# --------------------------------------------------------------------------- V6 independent proof


def _window_matches(stream: list[str], alt: list[str] | None, needle: list[str], start: int) -> bool:
    for k, tok in enumerate(needle):
        pos = start + k
        if stream[pos] == tok:
            continue
        if alt is not None and alt[pos] == tok:
            continue
        return False
    return True


def _contains_window(stream: list[str], alt: list[str] | None, needle: list[str]) -> bool:
    n, m = len(stream), len(needle)
    if m == 0 or m > n:
        return False
    first = needle[0]
    for i in range(n - m + 1):
        if (stream[i] == first or (alt is not None and alt[i] == first)) and _window_matches(
            stream, alt, needle, i
        ):
            return True
    return False


def _surah_stream(store: Store, g0: int, surah: int) -> tuple[list[str], list[str]]:
    """Strict (and twin-rasm) tokens from ``g0`` to the end of the surah's stream document, capped."""
    end = min(len(store.g_rec), g0 + MAX_PROOF_SPAN_TOKENS)
    doc = int(store.g_doc[g0])
    g = g0
    while g < end and int(store.g_doc[g]) == doc and store.records[int(store.g_rec[g])].surah == surah:
        g += 1
    n = g - g0
    return store.strict_tokens_range(g0, n), store.strict_alt_tokens_range(g0, n)


def _proof_streams(store: Store, rec: Record) -> list[tuple[list[str], list[str] | None]]:
    """Strict token streams a `found` quote must be a contiguous window of (any one suffices).

    Hadith: the record's own tokens. Quran: the surah stream from this ayah's first indexed token
    (after the basmala offset) to the end of the surah — covers cross-ayah quotes attributed to the
    ayah where the window starts (E-025) — in **each** rasm the index holds (Uthmani display stream
    and the simple-rasm stream, `g2_*`), each with its word-aligned twin (E-024). The two rasms are
    separate streams because 363 ayat differ in word count («يأيها» vs «يا أيها»); a quote in the
    simple rasm of such an ayah is provable only in its own stream.
    """
    if rec.corpus != "tanzil":
        return [(store.strict_tokens_of(rec), None)]
    out: list[tuple[list[str], list[str] | None]] = [
        _surah_stream(store, rec.g_start + rec.offset, rec.surah)
    ]
    if rec.g2_start >= 0 and rec.g2_len > 0:
        out.append(_surah_stream(store, rec.g2_start + rec.offset, rec.surah))
    return out


def prove_found(store: Store, q: QuoteResult) -> bool:
    """V6: True iff the quote's strict tokens are a contiguous window of the first match's record stream."""
    if not q.matches:
        return False
    rec = _lookup(store, q.matches[0])
    if rec is None:
        return False
    needle = strict_tokens(q.quoted_text)
    if not needle:
        return False
    return any(_contains_window(stream, alt, needle) for stream, alt in _proof_streams(store, rec))


def _unproven(q: QuoteResult) -> None:
    q.status = "needs_review"
    q.review_reason = "validator_unproven"
    q.message_key = "needs_review_unproven"
    q.notice_keys = [k for k in q.notice_keys if k != "quran_fragment"]


def _reject(q: QuoteResult) -> None:
    q.status = "needs_review"
    q.review_reason = "validator_reject"
    q.message_key = "needs_review_failure"
    q.matches = []
    q.notice_keys = [k for k in q.notice_keys if k in {"image_extracted"}]
    q.total_positions = 0
    q.score = 0.0


def validate_response(
    resp: CheckResponse, store: Store, messages_dir: Path, *, hadeethenc_link: bool = False
) -> CheckResponse:
    rejections = 0
    for q in resp.quotes:
        bad = False
        for m in q.matches:
            if not _match_ok(store, m, hadeethenc_link=hadeethenc_link):
                bad = True
                break
        if not bad:
            for s in _our_strings(q, messages_dir):
                if scan_forbidden(s):
                    bad = True
                    break
        if not bad and q.status == "found" and not q.matches:
            bad = True  # a `found` without a verbatim source is impossible
        if bad:
            _reject(q)
            rejections += 1
        elif q.status == "found" and not prove_found(store, q):  # V6
            _unproven(q)
            rejections += 1
    # V5
    ar = load_messages(messages_dir, "ar")
    if not (ar.has("fixed", resp.disclaimer_key) and ar.has("fixed", resp.transparency_key)):
        resp.disclaimer_key = "footer"
        resp.transparency_key = "transparency_notice"
    resp.validator_rejections = rejections
    return resp
