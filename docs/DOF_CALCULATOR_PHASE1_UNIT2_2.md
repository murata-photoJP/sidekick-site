# Sidekick DOF Calculator Phase 1 / Unit 2.2

## Purpose

The public calculator compares the latest successful calculation with the immediately preceding successful calculation. This is a UI-layer explanation of what changed; it does not modify the calculation model.

## Comparison semantics

- Input emphasis answers “what changed.” Result deltas answer “what changed by how much.”
- Before a value is confirmed, draft inputs are compared with the latest successful input while result cards remain unchanged.
- After a successful calculation, the former current record becomes previous and the new record becomes current. Only that adjacent pair is retained in memory.
- The initial calculation has no invented previous record. Reloading clears comparison history; URL, local storage, cookies, and server state are unchanged.

## Input confirmation model (2026-09-11 UX correction)

The explicit “計算する” (Calculate) submit button was removed. This is a UX correction to the public calculator, not a change to the comparison model above or to `calculation-core.mjs`.

- Unified rule: a calculation runs as soon as a value is confirmed, not while it is still being edited. Typing alone (the `input` event) only updates the “前回” draft-comparison markers; it never triggers a calculation.
- Numeric fields (focal length, F-number, focus distance, custom sensor/criterion values) confirm on the native `change` event — blur, Tab, or Enter — matching standard HTML form semantics.
- Enter needs one small addition beyond native `change`: browsers do not reliably fire `change` from Enter alone on a lone numeric input with no submit button in the form, so a minimal `keydown` fallback (Enter only, numeric inputs only) calls the same calculation path.
- F-number preset buttons and the sensor/criterion selects calculate immediately on click/selection; presets no longer require a separate confirmation step.
- A calculation is skipped (no history advance, no delta) when the confirmed input snapshot is identical to the last successful calculation’s snapshot. This both satisfies the “same value → no noisy zero delta” rule and makes any redundant double-fire (e.g. `change` and the Enter fallback landing on the same confirmed value) safe — the second call is a no-op rather than a duplicate history advance.
- Invalid confirmed values still run through the unchanged validation/error path; the last valid result and comparison history are preserved.

## Failure and infinity rules

- Invalid input displays validation feedback without clearing or advancing the last successful previous/current pair.
- Finite-to-infinity and infinity-to-finite far limits are state transitions, not numeric subtraction.
- Unchanged deltas are suppressed instead of filling the result panel with zero values.

## Accessibility

The neutral orange accent is accompanied by “前回”, arrows, numeric values, and accessible increase/decrease or finite/infinite labels. Native labels, keyboard controls, and focus-visible styling remain intact. Result updates use a polite, non-atomic live region.

## Test evidence

Unit tests cover first calculation, adjacent history advancement, normalized/free F-numbers, all requested input categories, invalid-history preservation, infinity transitions, zero suppression, and rounded non-color delta semantics. Site tests cover the rendered comparison hooks and controller safeguards.
