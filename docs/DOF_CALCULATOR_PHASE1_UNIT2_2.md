# Sidekick DOF Calculator Phase 1 / Unit 2.2

## Purpose

The public calculator compares the latest successful calculation with the immediately preceding successful calculation. This is a UI-layer explanation of what changed; it does not modify the calculation model.

## Comparison semantics

- Input emphasis answers “what changed.” Result deltas answer “what changed by how much.”
- Before submission, draft inputs are compared with the latest successful input while result cards remain unchanged.
- After a successful submission, the former current record becomes previous and the new record becomes current. Only that adjacent pair is retained in memory.
- The initial calculation has no invented previous record. Reloading clears comparison history; URL, local storage, cookies, and server state are unchanged.

## Failure and infinity rules

- Invalid input displays validation feedback without clearing or advancing the last successful previous/current pair.
- Finite-to-infinity and infinity-to-finite far limits are state transitions, not numeric subtraction.
- Unchanged deltas are suppressed instead of filling the result panel with zero values.

## Accessibility

The neutral orange accent is accompanied by “前回”, arrows, numeric values, and accessible increase/decrease or finite/infinite labels. Native labels, keyboard controls, and focus-visible styling remain intact. Result updates use a polite, non-atomic live region.

## Test evidence

Unit tests cover first calculation, adjacent history advancement, normalized/free F-numbers, all requested input categories, invalid-history preservation, infinity transitions, zero suppression, and rounded non-color delta semantics. Site tests cover the rendered comparison hooks and controller safeguards.
