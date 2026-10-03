# AGENTS.md — start here (humans and AI engineers)

> You are picking up **Basira (بصيرة)** in a fresh session, probably a fresh machine. This file gives you the whole
> memory of the project in ~15 minutes. **Do not write code before finishing §1–§4.**

## 0. One command to be productive

```bash
git clone https://github.com/alabasi2025/Project-Basira.git && cd Project-Basira
bash scripts/bootstrap.sh && make gates && make smoke     # ≈ 3 min → must end with SMOKE OK
make serve-mcp                                            # http://localhost:8000  (API + UI + MCP)
```
If `bootstrap` fails on tanzil.net TLS, that is upstream; `fetch.py` retries once with a loud warning and the sha256
pin still protects integrity (E-013).

## 1. Who you are, who the owner is

* **Owner**: the registered solo participant (`alabasi2025`). Decides product, policy, wording, design.
  Works through several AI agents in parallel and verifies with numbers. Speaks Arabic; code and paths in English.
* **You**: an engineering agent. You implement → verify by running → commit → merge to `main` → verify on `main`.
  The owner does not review PRs (D-001). Other agents may open PRs; **you re-run every claim before merging**
  (`docs/KNOWLEDGE.md` D3).
* **Attribution**: this is the owner's work; agents are disclosed as tools in `AI_USAGE.md` (D-006).

## 2. What Basira is, in one paragraph

Paste a text, an image, an English quotation, or a chatbot answer → Basira finds every passage *presented as*
Quran or Hadith → matches byte-exactly against licensed corpora (Tanzil ×3, Open-Hadith-Data 9 books, HadeethEnc,
QuranEnc/HadeethEnc translations) → returns one of **four states** (`found` / `partial_match` / `needs_review` /
`not_found`) with the verbatim source and a letter-level diff including vowel marks. A model may *propose where
quotes are* or *read an image*; it can never change a verdict or produce text the user sees. Every response carries a
`determinism_hash`; the same input on the same corpus build gives the same hash. Nothing is stored.

## 3. The rules you cannot break

1. **No generated religious text.** Display from the corpus by record id only.
2. **No judgment vocabulary.** Never صحيح / ضعيف / موضوع / محرّف / مكذوب / fatwa — `scripts/check_site_lexicon.py`
   and `messages.scan_forbidden` are gates, and they have caught *our own* copy (KNOWLEDGE B1). «لم يوجد في مصادرنا»
   is not a judgment.
3. **No storage.** No DB, no logs of user text, no per-request keys. The operator's model key is entered once on
   `/settings` and lives in one server file (E-051).
4. **`state.py` thresholds and V1–V5 semantics change only with an ADR** (`docs/adr/`).
5. **Every string the user sees comes from `messages/*.json` or `frontend/src/site/strings.ts`.** AR and EN key
   sets are identical (tested).
6. **Measured, never claimed.** Any number in docs/UI cites the command or file that produced it.
7. **Confidentiality**: `out/internal/` and anything derived from the organizer's non-public material never ships.
   `out/` is deleted before a public release.

## 4. Reading order (mandatory, ~15 min)

| # | File | Why |
|---|---|---|
| 1 | this file | role, rules, map |
| 2 | `docs/STATE.md` | where we are: every work package with its merge SHA and measured numbers |
| 3 | `docs/DECISIONS.md` | D-001…D-014 owner decisions, E-001…E-054 engineering decisions, dated, with reasons. **Never re-ask a decided question.** |
| 4 | `docs/KNOWLEDGE.md` | what broke and why — domain (Arabic/Quran encodings), safety wording, engineering, process |
| 5 | `SAFETY.md` | invariants I1–I17, validator V1–V6, red lines |
| 6 | `docs/ARCHITECTURE.md` | the pipeline, the developer gate, data, security posture |
| 7 | `docs/API.md` · `docs/INTEGRATIONS.md` · `docs/GUARD.md` · `docs/MODELS.md` | contracts and measured model data |
| 8 | `docs/adr/` | the five architecture decision records |
| 9 | `docs/ENGINEERING_PRACTICE.md` | how this project is run: context, prompts, parallel agents, verification |
| then | code: `backend/app/`, `frontend/src/`, `eval/`, `corpus/` | each module's docstring states *why* it exists |

## 5. Repository map

```
backend/app/
  main.py          FastAPI app, routes, security headers, rate limit, SPA, MCP mount, model config
  pipeline.py      the deterministic pipeline (extract → gates → retrieve → match → state → english → validate → hash)
  extract/         rules, corpus anchors, segments (isnad/matn/claimed source), foreign-material gate
  match/           exact windows, harakat comparison, diffs
  retrieve/        n-gram index, BM25 translations index
  verify.py        post-validator V1–V6 + attribution-only
  state.py         four-state machine (ADR-003) — do not touch without an ADR
  devgate.py / guard.py / guard_messages.py / mcp_server.py   REST+MCP core, Guard, MCP (6 tools)
  byok.py          server-side model configuration + measured catalog
  english_gate.py  English quotations → approved translations
  snapshot.py / store.py / normalize.py / schemas.py / messages.py
frontend/src/      React 19 + Vite + TS; site/ (pages, strings, router), components/, Check.tsx, api.ts
corpus/            manifest.json (sha256 pins), fetch.py, build_index.py, build_fixture.py   (data/, index/ ignored)
eval/              cases.yaml (150), false_alarm.py, run_eval.py, english eval, IslamicEval runners, REPORT.md
messages/          ar.json · en.json — single source of prose
scripts/           bootstrap.sh · smoke.py · mcp_demo.py · bench_models.py · check_site_lexicon.py · gen_*.py
docs/              STATE · DECISIONS · KNOWLEDGE · ARCHITECTURE · DEPLOYMENT · API · INTEGRATIONS · GUARD · MODELS · RISKS · GLOSSARY · adr/ · manual-test/
ci/                GitHub Actions workflow (move to .github/workflows/ — needs the `workflows` token scope)
out/               NOT the product: hand-offs, competition material, old notes. Delete before public release.
```

## 6. Per-session ritual

1. `make gates && make smoke` — green before anything else.
2. Read `docs/STATE.md` §"Open" and pick from there; if the owner gives new work, log the decision first.
3. Commit after every logical change (Conventional Commits); the sandbox is ephemeral — GitHub is the only
   persistence (D-011).
4. Before merging anything (yours or another agent's): `make lint && make test && make smoke && make eval-full &&
   git checkout eval/REPORT.md`, frontend `tsc && oxlint && vitest && build`, lexicon gate, and a **live** check in
   a browser or with `curl` for anything user-visible. Put the measured numbers in the merge message.
5. End of session: update `docs/STATE.md` (row per work package, with SHA and numbers), add `E-nnn` rows to
   `docs/DECISIONS.md`, add lessons to `docs/KNOWLEDGE.md`, push.

## 7. Working with the owner

* Answer in Arabic, keep code/paths in English. Be direct; the owner rejects vagueness and hidden scope.
* Show real output (terminal lines, screenshots), not descriptions of output.
* When the owner says "فقط X", build exactly X. When the owner rejects a design, do not iterate on it — ask or hand off.
* Owner decisions pending as of 2026-10-03 are listed at the end of `docs/KNOWLEDGE.md` §E.

## 8. Working with other agents

The owner runs several agents in parallel (design, backend features, audits). Protocol that worked:
hand them a prompt with (a) what to read first, (b) the exact deliverable, (c) the gates with expected numbers,
(d) what they must not touch, (e) "open a PR, do not merge". You verify and merge. Templates and the full method:
`docs/ENGINEERING_PRACTICE.md`.
