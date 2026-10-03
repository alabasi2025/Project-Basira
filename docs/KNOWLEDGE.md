# Knowledge base — what we learned the hard way

> Every entry below is tied to a real event in this repository (a failing test, a wrong output, an owner correction,
> a reviewer finding). Dates are 2026. Cross-references point to `DECISIONS.md` (E-/D- ids), `SAFETY.md` (I-/V- ids)
> and commits. Read this before touching the matcher, the messages, or the deployment.

## A. Domain — Arabic text, Quran, Hadith

| # | Lesson | Evidence | Where it lives now |
|---|---|---|---|
| A1 | **Two faithful encodings of the Mushaf can disagree byte-for-byte.** QuranEnc uses U+06E1 (small high dotless head of khah) for sukun where Tanzil uses U+0652; alif + combining madda U+0653 vs precomposed آ. Exact matching must run after *canonical composition*, not on raw code points. | mcp.islamiccontent.org `get_quran_verses` output was `not_found` until E-023 | `normalize.py` strict tier (E-023) |
| A2 | **Uthmani and simple rasm differ in word count for some ayat**, so "the quote is a contiguous window of the record" must be proven in **both** rasm streams or it rejects correct quotes. | V6 first version rejected 3/150 correct cases (A-010/011/013) | `verify.prove_found` (E-052) |
| A3 | **A final sukun on the last quoted word is waqf, not an error.** Every other vowel difference the user *wrote* is shown. The reference for vowels is Tanzil *simple* (fully vocalised), with per-word fallback to Uthmani display when alignment fails. | Owner decision D-013 after the 35:28 «اللهُ» / 39:53 cases; qurancomplex.gov.sa endpoint timed out → D-014 | `match/harakat.py::compare_words` |
| A4 | **A bare vowel-less quote carries no claim about vowels** — never report a "missing haraka" when the user wrote none. Only marks the user wrote are judged. | Gate test `أحد` bare → no notices | `_harakat_gate` |
| A5 | **Latin letters / digits inside a quote are foreign material, except ayah markers ﴿١﴾ and symbols ﷺ ﷻ ۞ ۝ ۩.** Before this gate, «قل هو HELLO الله أحد» came back `found`. | B02 failing-first test | `extract/foreign.py` (E-044) |
| A6 | **«رواه البخاري» is an attribution, not a quotation.** An isnad chain with no matn is not "found" even though the words exist verbatim in the book. Returning `not_found` with «لم يوجد في مصادرنا» would read as a judgment on Bukhari. | B05; first detector raised FA to 1/500 by misreading a cut isnad inside a Muslim record → tightened to *complete* chains | `verify.attribution_only_kind` (E-052) |
| A7 | **The same ayah text appears in several positions** (94:5/94:6, basmala 1:1 & 27:30, many hadith duplicated across ids). A claimed reference must be compared against *every* verbatim position before saying "mismatch"; duplicate candidates must be de-duplicated before asking a model to pick. | «[الرحمن: 77]» wrongly flagged (B06); picker probe picked the "wrong" twin | `pipeline._facts` (E-053); `PICK_SYSTEM` "lowest number among duplicates" |
| A8 | **Impossible references exist** («الإخلاص 1-999», «البقرة 300», reversed ranges). They are a notice, never a state change (I8). | B06 | `quran_meta.AYAH_COUNTS` (asserted = 6236 against Tanzil) |
| A9 | **Repeated quotes merge only when byte-identical.** Loose-key merging hid a second, *different* spelling of the same ayah in one text. | B03 | `pipeline.check` `seen_raw` (E-045) |
| A10 | **Image text is never `found`** regardless of OCR quality — OCR drops/alters harakat silently («على» vs «علي»). It is always `needs_review/orthographic_difference` with the read text echoed for the user to verify. | manual test I01 | E-020, `/v1/check/image` |

## B. Safety wording — the forbidden lexicon is a real gate, not a style guide

| # | Lesson | Evidence | Where |
|---|---|---|---|
| B1 | **Our own catalog notes failed the lexicon scanner.** "مواضع صحيحة", "قراءة سليمة", "مفتاح صحيحًا" were all rejected (stems صحيح / سليم are judgment words in this domain). Rewrite to «مطابقة», «سليم التنسيق». The scanner also runs on frontend strings (656) and on every MCP tool description. | `test_catalog_notes_pass_forbidden_scan` red on first run (2026-10-03) | `messages.scan_forbidden`, `scripts/check_site_lexicon.py` |
| B2 | **`not_found` is never red** and never phrased as a verdict. The badge colour, border and copy all say "not in our sources". | reviewer finding, E-032 | `StatusBadge`, `messages.status.not_found` |
| B3 | **Guard summaries must contain counts only** — no quoted religious text, Arabic number agreement (اقتباسان / 3 اقتباسات), footer «ليس حكمًا». They live in `guard_messages.py`, deliberately *outside* `messages/*.json` (different owner, different review path). | E-049 4-gram sweep | `guard_messages.py` |

## C. Engineering — things that broke and why

| # | Lesson | Evidence | Fix |
|---|---|---|---|
| C1 | **`app.mount("/", sub_app)` swallows the SPA catch-all.** With `BASIRA_MCP=1` the whole site returned 404 while all tests passed, because tests ran without `frontend/dist`. | found during the BYOK live check, 2026-10-03 | exact `Route("/mcp", endpoint=asgi_app)` + regression test with a fake `static_dir` |
| C2 | **Tests must not depend on whether `frontend/dist` exists.** A test expecting 404 got 405 when the SPA route existed. | `test_mcp_disabled_by_default_404` | `test_settings.static_dir=None` |
| C3 | **mmap'd snapshots keep ~15 fds open per app instance; 270+ tests hit the 1024 soft limit** → `OSError: Too many open files` in an unrelated test, intermittently. | `test_snapshot` red only in the full run | `conftest.py` raises `RLIMIT_NOFILE` soft limit |
| C4 | **A real key saved from `/settings` on the dev machine leaked into pytest** (`/health` showed the real provider). Any runtime file the app reads must be isolated per test process. | 3 tests red after a live demo | `conftest.py` sets `BASIRA_MODEL_CONFIG` to a temp path |
| C5 | **Read-only container + a feature that writes one file = broken feature.** The image declares `read_only: true`; `/settings` would have failed in production. | deployment audit, 2026-10-03 | `/data` volume, `BASIRA_MODEL_CONFIG=/data/model.json` |
| C6 | **Optional extras are a trap for CI and reviewers.** `mcp` is optional; mypy and pytest both fail at import time when it is missing, and the failure looks like 9 unrelated type errors. | PR #2 verification | `bootstrap.sh`, `Dockerfile`, `ci` all install `backend[dev,mcp]`; `test_mcp.py` skips when absent |
| C7 | **Reasoning effort is a latency knob, not a quality knob, for copy-work.** gpt-5.4: default 8.7–14.9 s, `none` 2.0–2.8 s, identical spans. | E-035 measurements | `LLM_REASONING_EFFORT=none` default in `serve.sh` |
| C8 | **Flagship ≠ best for a constrained task.** On the real extraction prompt gpt-5.4-mini scored 6/6 at 1.2 s / 0.3×; claude-opus-5-5 4/6 at 4.5 s / 4× and once refused the JSON format; claude-haiku-4-5 never returned JSON. Measure on *your* prompt. | 20-model benchmark | `docs/MODELS.md`, `scripts/bench_models.py` |
| C9 | **Upstream TLS certificates expire** (tanzil.net, 2026-09-30). With sha256 pins you can retry unverified *once*, loudly; integrity is still enforced by the pin. | bootstrap failed in a clean sandbox | `corpus/fetch.py` (E-013), `--strict-tls` |
| C10 | **Generated files must be reproducible or they are a lie.** `trust.json` and `examples.json` are regenerated in review and must produce zero diff. | PR #3 verification | `scripts/gen_trust.py`, `gen_examples.py`, CI step |
| C11 | **Decision ids collide when agents work in parallel.** Three branches each claimed E-047/E-050. Renumber at merge; the merger owns the sequence. | PRs #1, #3, #4 | `DECISIONS.md` E-047…E-054 |
| C12 | **A stacked PR must be rebased `--onto` the new base, not plain-rebased**, or git replays commits that already landed under new SHAs and conflicts on every file. | PR #5 on top of #4 | `git rebase --onto origin/main origin/<base-branch> <branch>` |

## D. Product & process

| # | Lesson | Evidence | Where |
|---|---|---|---|
| D1 | **"What is not built stays «قريبًا»" cuts both ways: what *is* built must not be hidden.** UI v3 shipped with English, Guard, MCP and the receipt marked "soon" while all four were live on `main`. Judges score what they can click. | E-054 | `site/services.ts` `live:` flags are the truth and are tested |
| D2 | **Owner's keys never travel per request.** The first BYOK design (header per call, key in localStorage) was rejected the same day. Enter once, verify, store on the server, mask everywhere. | E-051 rewrite | `byok.py` |
| D3 | **Verify agent claims by running them, not by reading them.** PR #2 claimed 238 tests / E-048; reality was 255 / E-049. PR #4 claimed 291; reality 293. Every merge message in this repo lists the numbers *the merger* measured. | merge commits e5f2213, 0eeae0d | `docs/STATE.md` rows |
| D4 | **Failing-first gates before design.** The owner refused any UI work until six adversarial cases failed, were fixed, and passed with real output. It caught B01–B03 in one afternoon. | 0db52fb | `tests/test_safety_gates.py` |
| D5 | **Every number shown to a user needs a source line.** The Trust page reads `eval/REPORT.md` by file+line; typing a number by hand is forbidden. | E-050 | `scripts/gen_trust.py` |

## E. Open questions (owner decisions still pending)

* **B01 final-vowel policy** needs a qira'at specialist + ADR before any change to D-013.
* **B05 scope**: 7 isnad chains inside hadith records currently read as `attribution_only` instead of `found` — kept (recommended) until the owner says otherwise.
* **B11** anything touching `state.py` thresholds requires an ADR (standing rule).
