# Sidekick DOF Calculator Phase 1 / Unit 2.2 — Codex to Claude Code Handoff

## 1. Canonical baseline

- FACT: repository `SideKick販売ページ/html`, branch `main`, upstream `origin/main`.
- FACT: Unit 2.1 closed commit and current HEAD are `3fcdda051c4e3d1b682c5c8d0f2eb06702fae6c1` (`fix(dof): refine public calculator UX`).
- FACT: `HEAD...origin/main` is `0/0`. Unit 2.1 history has not been altered.

## 2. Unit 2.2 purpose

Add previous-result comparison in the UI layer. The input side answers “what did I change?” and the result side answers “what changed, and by how much?” Calculation Core, research conclusions, and product semantics remain unchanged.

## 3. UX semantics

- IMPLEMENTED: first successful calculation shows current values without invented previous values or zero deltas.
- IMPLEMENTED: draft inputs are value-compared with the latest successful input; editing alone does not update result history.
- IMPLEMENTED: after success, the old current record becomes previous and the new record becomes current. A→B then B→C.
- IMPLEMENTED: invalid calculation displays an error without advancing or clearing the last valid comparison.
- IMPLEMENTED: Near, Focus, Far, DOF, Front, Rear, and Hyperfocal use `current - previous`; unchanged deltas are suppressed.
- IMPLEMENTED: finite/∞ transitions are semantic state changes and never numeric subtraction.
- IMPLEMENTED: neutral accent plus “前回”, arrows, values, and accessible increase/decrease labels; no good/bad color meaning.
- IMPLEMENTED: no persistence, URL schema change, or previous blur-curve overlay.

## 4. Current repository state

- FACT: HEAD `3fcdda051c4e3d1b682c5c8d0f2eb06702fae6c1`; `main`; `origin/main`; ahead/behind `0/0`.
- FACT before this handoff file: staged 0; six modified tracked Unit 2.2 files; three untracked Unit 2.2 files; no Git lock.
- FACT: no protected or unrelated file was found in the diff.
- FACT: no stage, commit, push, or deploy was performed for Unit 2.2.

## 5. Files changed

| File | Ownership and reason | State | Continue editing? |
|---|---|---|---|
| `assets/js/dof/calculator-ui.mjs` | Unit 2.2 controller/history/input/result rendering | IMPLEMENTED; visual integration NOT TESTED | Only for verified review findings |
| `assets/js/dof/comparison-state.mjs` | Pure value normalization, adjacent history, delta/∞ semantics | IMPLEMENTED and unit tested | No, unless tests reveal a defect |
| `assets/js/dof/formatters.mjs` | Rounded neutral distance-delta formatting | IMPLEMENTED and unit tested | No, unless formatting review fails |
| `assets/css/dof-calculator.css` | Neutral changed/previous/delta presentation and wrapping | IMPLEMENTED; responsive visual NOT TESTED | Yes, only if host visual review finds an issue |
| `templates/site/pages/dof.html` | Previous/delta DOM hooks and accessibility relationships | IMPLEMENTED; screen-reader behavior NOT TESTED | Yes, only for accessibility/visual findings |
| `tools/dof.html` | Canonical builder output from the template | IMPLEMENTED and parity tested | Do not hand-edit; regenerate from builder |
| `tests/tools/test_dof_comparison_state.mjs` | Unit 2.2 state and formatter regression tests | IMPLEMENTED; 10/10 PASS | Extend only for discovered defects |
| `tests/site/test_dof_page.py` | Rendered semantics/controller safeguard tests | IMPLEMENTED; included in pytest PASS | Extend only for discovered defects |
| `docs/DOF_CALCULATOR_PHASE1_UNIT2_2.md` | Purpose and semantic decision record | IMPLEMENTED | Update only with final review evidence |
| `docs/DOF_CALCULATOR_PHASE1_UNIT2_2_HANDOFF.md` | This factual handoff | IMPLEMENTED | Update with new verified facts only |

## 6. Implementation completed

- COMPLETE: first calculation, value-based input detection, draft/result separation, adjacent history advancement, invalid preservation, result deltas, infinity transitions, zero suppression, neutral/non-color semantics, non-persistence, URL compatibility, current-only curve.
- COMPLETE: template/generated asset versions are both `v=4`; generated output matches canonical rendering.
- COMPLETE: Calculation Core, URL module, blur-chart module, and Unit 1 golden fixtures are unchanged.

## 7. Implementation remaining

- REMAINING: host-browser functional and visual review at desktop, 375 px, and 320 px.
- REMAINING: verify no horizontal overflow, clipping, result-card/preset/button displacement, and that previous/delta hierarchy reads naturally.
- REMAINING: keyboard walkthrough and real screen-reader behavior. Static semantics are present, but these were not interactively tested.
- REMAINING: if review passes, perform a separate final close/commit gate only after explicit user authorization.

## 8. Tests executed

Actually executed by Codex during Unit 2.2:

- PASS: ES module syntax `7/7`.
- PASS: Unit 1 Node `15/15`.
- PASS: Unit 2/2.1/2.2 Node `26/26` (includes 10 new comparison tests).
- PASS: Research 07 self-tests `10/10`.
- PASS: targeted generated/template tests `12/12`.
- PASS: full pytest `435/435` (433→435 because two Unit 2.2 site tests were added).
- PASS: site validate-only `42 pages`.
- PASS: `git diff --check`.
- FAIL: none observed.

## 9. Tests remaining

- NOT TESTED: desktop browser visual/interaction review.
- NOT TESTED: 375 px and 320 px browser visual/interaction review.
- NOT TESTED: real screen-reader announcement behavior.
- NOT TESTED: end-to-end browser sequences A→B→C, invalid preservation, finite→∞, and ∞→finite. Their state helpers/static integration are tested, but not a live browser DOM session.

## 10. Known issues

- UNKNOWN: visual behavior in a real host browser. Codex in-app browser rejected the local `file:` page under its security policy; no bypass was attempted.
- PARTIAL: responsive and accessibility implementation is present and statically audited, but host visual and assistive-technology evidence is absent.
- FACT: PowerShell Git commands emit a permission warning for the user-level global ignore file; repository status output remains available. No repository configuration was changed.

## 11. Protected areas

Do not modify `assets/js/dof/calculation-core.mjs`, Unit 1 golden fixtures, Research 01–09, Research Archive, Coverage Audit, Product Specification, Python environment/requirements, taxonomy, `id_registry`, `web-published.json`, articles, unrelated site files, or repository/remote configuration. Do not change Near/Far/DOF/Hyperfocal/Infinity/CoC mathematics.

## 12. Exact next recommended action

1. Re-measure Git state and confirm only the ten Unit 2.2/handoff files listed here are dirty.
2. Read this document and the actual diff; do not reimplement completed behavior.
3. Open the generated `/tools/dof` page in a host browser and execute the required desktop/375/320, keyboard, invalid-history, and finite/∞ review sequences.
4. Change only a concrete failed review item. Regenerate `tools/dof.html` through `build/site/build_site.py`, then rerun affected and full regressions.
5. Leave stage/commit/push for a separately authorized close gate.

## 13. Stage/commit/push status

- FACT: staged `0`.
- FACT: Unit 2.2 is uncommitted.
- FACT: push and deploy were not performed.
- REMAINING: explicit user authorization is required before stage, commit, push, or deploy.
