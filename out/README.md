# `out/` — material that is **not part of the product**

Everything here is kept for provenance and the owner's records only. It is excluded from the Docker image
(`.dockerignore`), never imported by code, and not needed to run, test, deploy or judge Basira.

| Item | What it is | Why it is here |
|---|---|---|
| `extra/` | 500 files of earlier agent hand-offs, experiments, model analyses, reviews, old scripts (moved 2026-10-03, commit 817c6fb; see `extra/README.md`) | Historical working material; superseded by `docs/` |
| `internal/` | Competition assets (official PDFs, slides template, idea deck), technical and sharia review annexes, audit hand-off package | Owner-private; CLAUDE.md forbids publishing |
| `COMPETITION.md` | Our reading of the competition brief and judging criteria | Strategy note, not product |
| `UX_LOG.md` | UI iteration diary from the v3 design agent | Design process log |
| `handoffs_ui_v3.md` | The design agent's hand-off prompt for UI v3 | Agent-to-agent message |
| `START_HERE_NEXT_AGENT_old.md` | Previous onboarding note (replaced by `/AGENTS.md`) | Superseded |
| `brand-kit-README.md`, `brand-kit-LICENSE-NOTES.md` | Notes on the competition brand kit | Reference |
| `sandbox_ecosystem.config.cjs` | PM2 config used only inside the development sandbox | Not a deployment artefact (see `docs/DEPLOYMENT.md`) |

**Before publishing a clean repository for judging, delete this directory entirely** (`git rm -r out`).
