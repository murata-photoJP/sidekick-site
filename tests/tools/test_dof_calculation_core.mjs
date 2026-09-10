import assert from "node:assert/strict";
import test from "node:test";

import {
  CRITERION_PRESETS,
  DofValidationError,
  SENSOR_PRESETS,
  calculateClassicDof,
  calculateFarLimit,
  calculateHyperfocalMm,
  calculateNearLimitMm,
  evaluateCriterionAtDistance,
  resolveCriterionPreset,
  resolveSensorPreset,
  sampleContinuousCurve,
} from "../../assets/js/dof/calculation-core.mjs";
import { PHASE_1_GOLDEN_FIXTURES as VF } from "./dof_golden_fixtures.mjs";

const ABS_TOLERANCE_MM = 1e-6;
const ff = resolveSensorPreset("ff_36x24");

function close(actual, expected, tolerance = ABS_TOLERANCE_MM) {
  assert.ok(Math.abs(actual - expected) <= tolerance, `expected ${actual} to be within ${tolerance} of ${expected}`);
}

function inputFrom(fixture) {
  return {
    sensor: ff,
    focalLengthMm: fixture.focalLengthMm,
    fNumber: fixture.fNumber,
    focusDistanceMm: fixture.focusDistanceMm,
    criterion: { ...CRITERION_PRESETS.traditional_ff_0030, valueMm: fixture.criterionMm },
  };
}

for (const id of ["VF01", "VF02", "VF03", "VF04"]) {
  test(`${id}: canonical near/far result`, () => {
    const fixture = VF[id];
    const result = calculateClassicDof(inputFrom(fixture));
    close(result.nearMm, fixture.nearMm);
    if (fixture.farIsInfinite) {
      assert.equal(result.farMm, null);
      assert.equal(result.farIsInfinite, true);
    } else {
      close(result.farMm, fixture.farMm);
      close(result.totalDofMm, fixture.totalDofMm);
    }
    if (fixture.frontDofMm !== undefined) close(result.frontDofMm, fixture.frontDofMm);
  });
}

test("VF05: hyperfocal retains the +f term", () => {
  close(calculateHyperfocalMm(VF.VF05), VF.VF05.hyperfocalMm, 1e-12);
});

test("VF06: focus at H gives H/2 near and infinite far", () => {
  const result = calculateClassicDof(inputFrom(VF.VF06));
  close(result.nearMm, VF.VF06.nearMm, 1e-12);
  assert.equal(result.farMm, null);
  assert.equal(result.farIsInfinite, true);
});

test("VF07: zero and negative far denominators never return a negative distance", () => {
  const atBoundary = calculateClassicDof(inputFrom(VF.VF06));
  assert.equal(atBoundary.farMm, null);
  assert.equal(atBoundary.farIsInfinite, true);
  const beyondBoundary = calculateClassicDof(inputFrom({ ...VF.VF06, focusDistanceMm: 3000 }));
  assert.equal(beyondBoundary.farMm, null);
  assert.equal(beyondBoundary.farIsInfinite, true);
});

test("VF08: macro warning is explicitly a thin-lens MODEL estimate", () => {
  const result = calculateClassicDof(inputFrom({ ...VF.VF08, fNumber: 8, criterionMm: 0.030 }));
  close(result.magnificationEstimate.value, VF.VF08.modelMagnification, 1e-12);
  assert.equal(result.magnificationEstimate.evidenceState, "MODEL");
  assert.equal(result.magnificationEstimate.realLensMagnificationState, "UNKNOWN");
  assert.ok(result.warnings.some((warning) => warning.code === VF.VF08.warningCode));
});

test("VF09 and VF10 remain explicit Phase 2 fixtures", () => {
  assert.deepEqual([VF.VF09.status, VF.VF10.status], ["DEFERRED", "DEFERRED"]);
  assert.deepEqual([VF.VF09.phase, VF.VF10.phase], [2, 2]);
});

test("VF11: focus distance at or below focal length is blocked", () => {
  for (const focusDistanceMm of [50, 49, 0, Number.NaN, Number.POSITIVE_INFINITY]) {
    assert.throws(
      () => calculateClassicDof(inputFrom({ ...VF.VF02, focalLengthMm: 50, focusDistanceMm })),
      DofValidationError,
    );
  }
});

test("VF12: curve crossings equal the VF02 closed-form limits", () => {
  const input = inputFrom(VF.VF02);
  const curve = sampleContinuousCurve(input, { startObjectDistanceMm: 2000, endObjectDistanceMm: 4000, sampleCount: 9 });
  close(curve.crossings.nearMm, VF.VF02.nearMm);
  close(curve.crossings.farMm, VF.VF02.farMm);
  close(calculateNearLimitMm(input), VF.VF02.nearMm);
  close(calculateFarLimit(input).farMm, VF.VF02.farMm);
  close(evaluateCriterionAtDistance(input, curve.crossings.nearMm).marginMm, 0, 1e-15);
  close(evaluateCriterionAtDistance(input, curve.crossings.farMm).marginMm, 0, 1e-15);
  assert.equal(curve.requestedSampleCount, 9);
  assert.equal(curve.samples.length, 9);
});

test("criterion margin is c-b and its sign controls criterionMet", () => {
  const input = inputFrom(VF.VF02);
  const focus = evaluateCriterionAtDistance(input, 3000);
  close(focus.blurMm, 0, 1e-15);
  close(focus.marginMm, 0.030, 1e-15);
  assert.equal(focus.criterionMet, true);
  const outside = evaluateCriterionAtDistance(input, 2600);
  assert.ok(outside.marginMm < 0);
  assert.equal(outside.criterionMet, false);
});

test("sensor presets and criterion presets are separate data", () => {
  assert.equal(Object.keys(SENSOR_PRESETS).length, 5);
  assert.deepEqual([ff.widthMm, ff.heightMm], [36, 24]);
  const mft = resolveSensorPreset("mft_173x130");
  const traditional = resolveCriterionPreset("traditional_ff_0030", { sensor: mft });
  assert.equal(traditional.valueMm, 0.030, "Traditional reference must not auto-scale with format");
  const diagonal = resolveCriterionPreset("format_diagonal_1500", { sensor: mft });
  close(diagonal.valueMm, Math.hypot(17.3, 13.0) / 1500, 1e-15);
});

test("invalid finite/positive inputs and sensor dimensions are never defaulted", () => {
  const valid = inputFrom(VF.VF02);
  for (const [field, value] of [
    ["focalLengthMm", 0], ["focalLengthMm", Number.NaN], ["fNumber", -1], ["fNumber", Number.POSITIVE_INFINITY],
  ]) {
    assert.throws(() => calculateClassicDof({ ...valid, [field]: value }), DofValidationError);
  }
  assert.throws(() => calculateClassicDof({ ...valid, criterion: { ...valid.criterion, valueMm: 0 } }), DofValidationError);
  assert.throws(() => calculateClassicDof({ ...valid, sensor: { presetId: "custom", widthMm: 0, heightMm: 24 } }), DofValidationError);
});

test("curve sampling count and range are caller-controlled and validated", () => {
  const input = inputFrom(VF.VF02);
  assert.equal(sampleContinuousCurve(input, { startObjectDistanceMm: 1000, endObjectDistanceMm: 5000, sampleCount: 3 }).samples.length, 3);
  assert.throws(() => sampleContinuousCurve(input, { startObjectDistanceMm: 1000, endObjectDistanceMm: 5000, sampleCount: 1 }), DofValidationError);
  assert.throws(() => sampleContinuousCurve(input, { startObjectDistanceMm: 5000, endObjectDistanceMm: 1000, sampleCount: 3 }), DofValidationError);
});
