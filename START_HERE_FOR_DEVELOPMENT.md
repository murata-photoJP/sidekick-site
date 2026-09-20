# START HERE FOR DEVELOPMENT — sidekick-site（Sidekick Lab Web、Web 版 Sidekick DOF を含む）

**If you are an AI development worker, read this file completely before modifying anything.**

This repository is the **canonical source of the Sidekick Lab website** (`https://www.sidekick-lab.com`), including the
**Web version of Sidekick DOF** (`/tools/dof`, `/en/tools/dof`). It is a static site: hand-written and Jinja2-generated HTML,
CSS, browser-native ES modules; Python is used only for builds, tests and repository tools; Vercel serves the committed files as-is.
（日本語：このリポジトリは Sidekick Lab サイトの正本。Web 版 DOF 計算機を含む。Vercel は build せず commit 済み HTML を配信する。）

## 0. Repository identity and copies

| what | value |
|---|---|
| canonical Git remote | `origin` = `https://github.com/murata-photoJP/sidekick-site.git`, branch `main` (push to `main` = production deploy) |
| local working copy | `…\自作\SideKick販売ページ\html\` — a separate git repository; the parent folder is excluded from the `jisaku` (`自作`) repository and its NAS bare repository |
| NAS backup | `Z:\mahoroba999\ProgramSoce\自作\SideKick販売ページ\` — manual robocopy file copy of the whole parent folder including this repository's `.git` (see `docs/WEB_RECOVERY_AND_BACKUP.md`) |
| deployment | Vercel project `sidekick-site-tawny.vercel.app`, domain `www.sidekick-lab.com`, `vercel.json` (`cleanUrls`, redirects), `.vercelignore` (what is NOT served) |

Repository First before any change: `git status`, `git fetch origin`, ahead / behind vs `origin/main`, staged / unstaged / untracked,
locks / merge / rebase, other sessions' work in progress (never touch it). Rules of the workspace: `../../CLAUDE.md` (the `自作` repository);
explicit-path staging only, no `git add -A`, `reset --hard`, `stash`, `clean`, `rebase`.

## 1. Read next

1. `docs/DEPLOY_CHECKLIST.md` — Python 3.12 `.venv`, `requirements-test.txt`, the 4 template→HTML build systems, `pytest tests -q` (5 suites), deploy policy.
2. `docs/WEB_RECOVERY_AND_BACKUP.md` — where the copies are, NAS backup mechanism (manual, freshness-dependent), restore procedures, security boundary.
3. For Web DOF: `docs/DOF_CALCULATOR_PHASE1_UNIT1.md` → `UNIT2.md` → `UNIT2_2.md` → `UNIT2_2_HANDOFF.md` (scope, decisions, what is Phase 2 / not implemented).
4. The other build docs as needed: `KNOWLEDGE_BUILD.md`, `DEVELOPMENT_LOG_BUILD.md`, `STORY_BUILD.md`, `CHANGELOG_WORKFLOW.md`, `DOWNLOAD_CONTACTS.md`.
5. For the Sidekick Planner product page and its (fail-closed) download flow: `docs/PLANNER_PRODUCT_PAGE.md` (2026-09-20).
6. For where the Planner ZIP is hosted (same R2 bucket as Star) and the Human-GO release steps: `docs/PLANNER_DISTRIBUTION.md` (2026-09-20).

## 2. Web DOF — source map (actual import / route dependencies, verified 2026-09-16)

| layer | files |
|---|---|
| public pages | `tools/dof.html` (`/tools/dof`), `en/tools/dof.html` (`/en/tools/dof`) — **generated**; never hand-edit |
| templates / builder | `templates/site/pages/dof.html`, `templates/site/pages/en/dof.html`, `build/site/build_site.py` (`PAGES["dof"]`, `PAGES["en/dof"]`; shared header/footer from `templates/knowledge/`) |
| modules | `assets/js/dof/calculator-ui.mjs` (entry) → `calculation-core.mjs` (**the calculation core**: sensor / criterion presets, validation, near / far / hyperfocal, curve sampling), `blur-chart.mjs`, `comparison-state.mjs` (previous-result comparison), `formatters.mjs`, `input-values.mjs`, `url-state.mjs` (URL sharing) |
| styles | `assets/css/dof-calculator.css` (+ shared `assets/css/site-header.css`) |
| tests | `tests/tools/test_dof_calculation_core.mjs`, `test_dof_comparison_state.mjs`, `test_dof_url_state.mjs` (Node built-in runner: `node --test tests/tools/<file>`; Node version is not pinned), `tests/tools/dof_golden_fixtures.mjs` (**golden fixtures VF01–VF12**), `tests/site/test_dof_page.py` (template ↔ generated HTML) |
| external services | **none** — the DOF page uses no Firebase, API, analytics or fetch. `firebase-init.js` / `api/` belong to other pages (AI Lab, downloads) |

Build / check: `.\.venv\Scripts\python.exe build/site/build_site.py --output build-output/site --validate-only`, then `pytest tests -q`.
Local preview: the site is plain static files — serve the repository root with any static file server (there is no bundler / dev server).

## 3. Windows product and the parity contract

**A Windows desktop version (Sidekick DOF Desktop) exists** in the `自作` repository at `Sidekickシリーズ/本体/SidekickDOF/`
(branch `track/product-sidekick-dof` until merged; Human Review deployment with a Long-term Maintenance Package at
`…\自作\Sidekickシリーズ\本体\SidekickDOF\` — read its `START_HERE_FOR_DEVELOPMENT.md`).

- Its Classic core `src/sidekick_dof/core/classic.py` is a **1:1 port of this repository's `assets/js/dof/calculation-core.mjs`**
  (ported from commit `740436d`; the sha256 of the ported file is recorded in that Python file's docstring), and its
  `fixtures/golden/classic_vf.json` is a copy of `tests/tools/dof_golden_fixtures.mjs` (source commit and sha256 recorded inside).
- **This repository is the canonical calculation source for Classic.** The Windows product must not re-implement or change the formulas;
  if `calculation-core.mjs` or the golden fixtures change here, the Windows port and fixtures must be re-derived and re-verified
  (`tests/test_classic_parity.py` on the Windows side). Divergence is detected only by comparing those recorded hashes — there is no
  automatic cross-repository check.
- Previous-result comparison (`comparison-state.mjs`), auto-calculate (`calculator-ui.mjs`) and formatting (`formatters.mjs`) are also the
  behavioural contracts the Windows UI follows. Portrait / Close-up reverse calculation exist only on Windows (Web Phase 2, not implemented).

## 4. Research and product specification (canonical, outside this repository)

The calculation, criterion and model boundaries come from the canonical Research Packets in the `自作` repository:
`_SideKick_Development/docs/HISTORY/Research_Packet/` — for Web DOF: RP-2026-005 (CoC 0.030 mm / format-diagonal criterion provenance),
RP-2026-011 (geometric DOF model; validation code `code/RP-2026-011/geometric_dof_model.py`), RP-2026-021 (CoC end-to-end / viewing conditions),
and the MVP Product Specification `Research_Packet/SIDEKICK_DOF_CALCULATOR_MVP_PRODUCT_SPECIFICATION.md`. The Windows package's
`MaintenanceDocs/RESEARCH_DEPENDENCIES.md` is a feature → RP-section index. The core carries `provenanceId` / `evidenceState`
(FACT / DERIVATION / MODEL / REFERENCE / ASSUMED / UNKNOWN) — keep them exactly as the Research states; do not change formulas, criteria or
model boundaries without reading the canonical RP, and never fill Research UNKNOWNs by guessing.

## 5. Backup / recovery rule

- Before and after a work session, check the NAS backup freshness (READ ONLY): `py -3.10 -B tools/check_nas_backup_status.py`
  → `CURRENT` / `STALE` (n commits behind) / `UNAVAILABLE`. **Running the backup (`☆☆☆nas_backup.bat`) is a Human decision** — AI workers do not run it.
- Restore procedures and the role split (GitHub = public/canonical Git remote; NAS file copy = private disaster-recovery backup including local-only state):
  `docs/WEB_RECOVERY_AND_BACKUP.md`.
- **Security boundary: private / local-only files may exist in the parent folder and must never be committed to GitHub.** Do not read, print or copy
  secret values; environment variables live in Vercel only (names: see `docs/WEB_RECOVERY_AND_BACKUP.md` §5).

## 6. Do not

- Do not hand-edit generated pages (`tools/dof.html` etc.); change the template and rebuild (`docs/DEPLOY_CHECKLIST.md` §1).
- Do not push to `main` without a Human decision — a push is a production deployment.
- Do not touch `.vercelignore` / `.gitignore` exclusions without checking references (the header of `.vercelignore` explains why).
- Do not treat this file as a specification: the DOF specification is the MVP Product Specification + `docs/DOF_CALCULATOR_PHASE1_*.md`.
