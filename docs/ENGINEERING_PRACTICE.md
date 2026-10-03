# Engineering practice — how Basira was built

> This document is for reviewers who want to know *how* the work was done, not only *what* was shipped. Every
> claim points at an artefact in this repository. It describes four disciplines the owner applied and the evidence
> they left: **software engineering**, **context engineering**, **prompt engineering**, and **agent engineering**
> (orchestrating several AI agents in parallel under one direction).

## 0. The numbers (as of 2026-10-03, `main`)

| Dimension | Measure |
|---|---|
| Code | ≈ 8 100 lines Python (`backend/app`), ≈ 7 900 lines TS/CSS (`frontend/src`) |
| Tests | 304 backend (ruff + mypy strict), 26 frontend; failing-first tests for every reported defect |
| Evaluation | 150 adversarial cases × 3 repeats, variance 0; 500 false-alarm probes, 0 hits; 20 models benchmarked on the real prompt |
| Decisions | 68 dated decision rows (`docs/DECISIONS.md`: 14 owner `D-`, 54 engineering `E-`), 5 ADRs |
| Delivery | 90 commits, 8 verified `--no-ff` merges, 5 agent PRs integrated after re-running every stated number |
| Prose discipline | 86 message keys (AR = EN sets, tested) + 458 site strings, all scanned for judgment vocabulary (0 hits) |
| Time | research + prototype before 4 Oct; the product in its current form was built in the challenge window |

## 1. Software engineering

**Determinism as the architecture.** The core promise — same input, same corpus build, same answer — is enforced
by code, not by policy: a two-tier normaliser, byte-exact windows, a post-validator that re-proves every `found`
independently of the matcher (V6), and a `determinism_hash` on every response that a judge can recompute.
(`docs/ARCHITECTURE.md` §2; `backend/app/verify.py::prove_found`.)

**Failing-first gates.** Before any design work was allowed, six adversarial inputs had to fail, be fixed, and pass
with real output (foreign token inside an ayah, wrong vowel on «الله», missing vowel, waqf sukun, false alarms,
150/150). The tests are still in the tree: `backend/tests/test_safety_gates.py`. (`docs/KNOWLEDGE.md` D4.)

**Measured, never claimed.** The trust page is *generated* from `eval/REPORT.md` with file + line provenance
(`scripts/gen_trust.py`); the model catalog on `/settings` is generated from a benchmark that ran on this
repository's own prompt (`docs/MODELS.md`, `scripts/bench_models.py`). Hand-typed numbers are forbidden
(`CONTRIBUTING.md` §5).

**Single source of prose.** Every user-facing sentence lives in `messages/{ar,en}.json` or
`frontend/src/site/strings.ts`, with an automated lexicon gate that caught the project's own copy three times
(`docs/KNOWLEDGE.md` B1). AR/EN key parity is a test.

**Security by default.** CSP with hashed inline script, COOP/CORP, HSTS, trusted-proxy `X-Forwarded-For`, image
magic-byte sniffing, bounded zlib inflate for receipt tokens, read-only container, non-root user, pip-audit and
npm audit at 0. (`SECURITY.md`, `docs/DEPLOYMENT.md`.)

**Reproducible data.** Every corpus file is sha256-pinned in `corpus/manifest.json`; the index fingerprint is in
`/health`; the Docker image builds the snapshot at image time so the deployed artefact is bit-identical to what
was tested.

## 2. Context engineering

The owner's operating model is **"every day = new account, new sandbox, new agent; GitHub is the only memory"**
(`DECISIONS.md` D-011). That forced a repository that *is* the context:

* **Layered entry**: `AGENTS.md` (15-minute full memory) → `docs/STATE.md` (where we are, per work package, with
  SHA and numbers) → `docs/DECISIONS.md` (what was decided and why — "never re-ask a decided question") →
  `docs/KNOWLEDGE.md` (what broke and why) → ADRs → code. A new agent in a fresh sandbox was productive within
  one bootstrap command on three separate occasions (`STATE.md` §0, verified 2026-09-30, 10-01, 10-03).
* **Decisions as first-class artefacts.** 68 dated rows with *what / why / where*. When three parallel agents
  claimed the same decision id, the integrator renumbered at merge and recorded the collision
  (`KNOWLEDGE.md` C11).
* **Separation of product and provenance.** Everything an agent needed historically but a judge does not
  (hand-off prompts, experiments, model research, competition material) lives under `out/` with a table
  explaining each item (`out/README.md`), excluded from the image, deletable in one command.
* **Glossary and bilingual discipline.** `docs/GLOSSARY.md` fixes the AR/EN terms; answers to the owner are in
  Arabic, code and paths in English (`AGENTS.md` §7).

## 3. Prompt engineering

Prompts in this project are **constrained interfaces**, not conversations, and each is tested like code:

* **Extraction prompt** (`providers/openai_compat.py::EXTRACT_SYSTEM`): the model may only *copy* passages
  presented as quotations, in strict JSON; every proposal is relocated to a verbatim substring or dropped
  (`relocate()`), so a hallucinated span has no effect. 20 models were benchmarked on this prompt with six inputs
  designed to catch the two classic failures — inventing a quote in plain prose, and listing an attribution
  («رواه البخاري») as a quote (`docs/MODELS.md`).
* **Picker prompt** (`PICK_SYSTEM`): the model returns `{"pick": k}` or `0` — an index into *approved*
  translations, never text. After the first probe revealed duplicate passages (94:5/94:6, duplicate hadith ids),
  the prompt gained "answer the LOWEST number among duplicates"; result: 0 wrong selections across 3 models on
  23 cases + 7 negatives (`eval/run_english_picker.py`).
* **Latency as a prompt parameter.** Reasoning effort was measured, not assumed: for copy-work, `none` cut
  gpt-5.4 from 9–15 s to 2–3 s with identical spans (E-035).
* **Grounding rules for downstream assistants** are a fixed text drawn from `SAFETY.md`, exposed as an MCP tool
  (`grounding_rules`) with its own sha256, so an assistant using Basira cannot "improve" the wording.

## 4. Agent engineering

The owner ran **several agents in parallel** — a design agent, two backend agents, an auditor — under one
integrator. What made it work is visible in the repository:

* **Work orders with gates.** Each agent received a prompt specifying (a) files to read first, (b) the exact
  deliverable, (c) the acceptance gates *with expected numbers*, (d) files it must not touch, (e) "open a PR,
  do not merge". Examples: the design hand-off (`out/handoffs_ui_v3.md`), the dev-gate order (E-049), the
  receipt order (E-052).
* **Verify-then-merge, with the integrator's numbers.** Every merge message on `main` lists the gates the
  *integrator* ran, not the ones the agent reported — and the two differed every time (238 vs 255 tests on PR #2;
  291 vs 293 on PR #4). Discrepancies are recorded in `docs/STATE.md`.
* **Non-overlapping scopes, enforced.** Agents were given disjoint directories (`match/`, `extract/`,
  `pipeline.py`, `state.py`, `frontend/` were off-limits to backend agents and vice-versa); each PR review begins
  with `git diff --name-only` against the forbidden list (merge messages for PRs #4 and #5).
* **Stacked work handled correctly.** PR #5 was built on PR #4; it was rebased `--onto main` past the already
  merged commits instead of replaying them (`KNOWLEDGE.md` C12).
* **Owner as the decision authority, agents as executors.** When the owner rejected a design (twice) or a
  security model (per-request keys), the agent did not iterate on the rejected idea; it rebuilt to the stated
  constraint the same day (`DECISIONS.md` E-051 "first iteration rejected and removed").
* **The repository is the inbox.** Hand-offs, prompts and review artefacts were committed, so a new agent can
  reconstruct the conversation from git alone — the only persistence the owner allowed.

## 5. What this demonstrates, in one sentence each

* **Software engineering**: a deterministic, independently verifiable product with 330 tests, zero false alarms
  and a reproducible build.
* **Context engineering**: a repository that re-hydrates a fresh agent to full productivity in one command.
* **Prompt engineering**: model interfaces reduced to typed, testable contracts and benchmarked across 20 models.
* **Agent engineering**: parallel agents with disjoint scopes, gated work orders, and verify-then-merge
  integration — five PRs landed in one day with every number re-measured.
