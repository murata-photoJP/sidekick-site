/**
 * Sidekick DOF Calculator Phase 1 calculation core.
 *
 * Canonical units are millimetres for every length and a dimensionless
 * f-number. This module deliberately contains no display rounding or UI text.
 * Results describe an ideal paraxial thin-lens MODEL tested against a selected
 * criterion; they are not a human sharpness verdict or a real-lens prediction.
 */

export const EVIDENCE_STATES = Object.freeze([
  "FACT",
  "DERIVATION",
  "MODEL",
  "REFERENCE",
  "ASSUMED",
  "UNKNOWN",
  "BYPASSED",
]);

export const GEOMETRIC_MODEL = Object.freeze({
  id: "ideal_paraxial_thin_lens",
  evidenceState: "MODEL",
  distanceReference: "front_principal_plane",
  realLensPrincipalPlaneState: "UNKNOWN",
});

export const SENSOR_PRESETS = Object.freeze({
  ff_36x24: Object.freeze({ presetId: "ff_36x24", widthMm: 36.0, heightMm: 24.0, evidenceState: "REFERENCE" }),
  apsc_canon_ref: Object.freeze({ presetId: "apsc_canon_ref", widthMm: 22.3, heightMm: 14.9, evidenceState: "REFERENCE" }),
  apsc_235x156_ref: Object.freeze({ presetId: "apsc_235x156_ref", widthMm: 23.5, heightMm: 15.6, evidenceState: "REFERENCE" }),
  mft_173x130: Object.freeze({ presetId: "mft_173x130", widthMm: 17.3, heightMm: 13.0, evidenceState: "REFERENCE" }),
  custom: Object.freeze({ presetId: "custom", widthMm: null, heightMm: null, evidenceState: "REFERENCE" }),
});

export const CRITERION_PRESETS = Object.freeze({
  traditional_ff_0030: Object.freeze({
    presetId: "traditional_ff_0030",
    metric: "geometric_support_diameter",
    valueMm: 0.030,
    direction: "lte",
    evidenceState: "REFERENCE",
    provenanceId: "RP-2026-005",
  }),
  format_diagonal_1500: Object.freeze({
    presetId: "format_diagonal_1500",
    metric: "geometric_support_diameter",
    valueMm: null,
    direction: "lte",
    evidenceState: "REFERENCE",
    provenanceId: "RP-2026-005",
    derivation: "sensor_diagonal_mm/1500",
  }),
  custom: Object.freeze({
    presetId: "custom",
    metric: "geometric_support_diameter",
    valueMm: null,
    direction: "lte",
    evidenceState: "REFERENCE",
    sourceType: "USER",
  }),
});

export class DofValidationError extends Error {
  constructor(issues) {
    super(`Invalid DOF input: ${issues.map((issue) => issue.code).join(", ")}`);
    this.name = "DofValidationError";
    this.issues = issues;
  }
}

function isPositiveFinite(value) {
  return Number.isFinite(value) && value > 0;
}

export function resolveSensorPreset(presetId, customDimensions = {}) {
  const preset = SENSOR_PRESETS[presetId];
  if (!preset) {
    throw new DofValidationError([{ field: "sensor.presetId", code: "UNKNOWN_SENSOR_PRESET" }]);
  }
  if (presetId !== "custom") return { ...preset };
  const sensor = {
    ...preset,
    widthMm: customDimensions.widthMm,
    heightMm: customDimensions.heightMm,
  };
  validateSensor(sensor);
  return sensor;
}

export function validateSensor(sensor) {
  const issues = [];
  if (!sensor || typeof sensor !== "object") {
    issues.push({ field: "sensor", code: "SENSOR_REQUIRED" });
  } else {
    if (!isPositiveFinite(sensor.widthMm)) issues.push({ field: "sensor.widthMm", code: "INVALID_SENSOR_WIDTH" });
    if (!isPositiveFinite(sensor.heightMm)) issues.push({ field: "sensor.heightMm", code: "INVALID_SENSOR_HEIGHT" });
  }
  if (issues.length) throw new DofValidationError(issues);
  return sensor;
}

export function resolveCriterionPreset(presetId, options = {}) {
  const preset = CRITERION_PRESETS[presetId];
  if (!preset) {
    throw new DofValidationError([{ field: "criterion.presetId", code: "UNKNOWN_CRITERION_PRESET" }]);
  }
  if (presetId === "traditional_ff_0030") return { ...preset };
  if (presetId === "format_diagonal_1500") {
    const sensor = validateSensor(options.sensor);
    return { ...preset, valueMm: Math.hypot(sensor.widthMm, sensor.heightMm) / 1500 };
  }
  const criterion = { ...preset, valueMm: options.valueMm };
  validateCriterion(criterion);
  return criterion;
}

export function validateCriterion(criterion) {
  if (!criterion || typeof criterion !== "object") {
    throw new DofValidationError([{ field: "criterion", code: "CRITERION_REQUIRED" }]);
  }
  if (!isPositiveFinite(criterion.valueMm)) {
    throw new DofValidationError([{ field: "criterion.valueMm", code: "INVALID_CRITERION" }]);
  }
  if (criterion.direction !== "lte") {
    throw new DofValidationError([{ field: "criterion.direction", code: "UNSUPPORTED_CRITERION_DIRECTION" }]);
  }
  return criterion;
}

export function validateClassicInput(input) {
  const issues = [];
  try { validateSensor(input?.sensor); } catch (error) { issues.push(...error.issues); }
  try { validateCriterion(input?.criterion); } catch (error) { issues.push(...error.issues); }

  if (!isPositiveFinite(input?.focalLengthMm)) issues.push({ field: "focalLengthMm", code: "INVALID_FOCAL_LENGTH" });
  if (!isPositiveFinite(input?.fNumber)) issues.push({ field: "fNumber", code: "INVALID_F_NUMBER" });
  if (!Number.isFinite(input?.focusDistanceMm)) issues.push({ field: "focusDistanceMm", code: "INVALID_FOCUS_DISTANCE" });
  else if (Number.isFinite(input?.focalLengthMm) && input.focusDistanceMm <= input.focalLengthMm) {
    issues.push({ field: "focusDistanceMm", code: "FOCUS_DISTANCE_NOT_GREATER_THAN_FOCAL_LENGTH" });
  }
  if (issues.length) throw new DofValidationError(issues);
  return input;
}

export function calculateHyperfocalMm({ focalLengthMm, fNumber, criterionMm }) {
  if (!isPositiveFinite(focalLengthMm)) throw new DofValidationError([{ field: "focalLengthMm", code: "INVALID_FOCAL_LENGTH" }]);
  if (!isPositiveFinite(fNumber)) throw new DofValidationError([{ field: "fNumber", code: "INVALID_F_NUMBER" }]);
  if (!isPositiveFinite(criterionMm)) throw new DofValidationError([{ field: "criterionMm", code: "INVALID_CRITERION" }]);
  return (focalLengthMm ** 2) / (fNumber * criterionMm) + focalLengthMm;
}

export function calculateGeometricBlurMm({ objectDistanceMm, focalLengthMm, fNumber, focusDistanceMm }) {
  if (!isPositiveFinite(objectDistanceMm) || objectDistanceMm <= focalLengthMm) {
    throw new DofValidationError([{ field: "objectDistanceMm", code: "OBJECT_DISTANCE_NOT_GREATER_THAN_FOCAL_LENGTH" }]);
  }
  if (!isPositiveFinite(focalLengthMm)) throw new DofValidationError([{ field: "focalLengthMm", code: "INVALID_FOCAL_LENGTH" }]);
  if (!isPositiveFinite(fNumber)) throw new DofValidationError([{ field: "fNumber", code: "INVALID_F_NUMBER" }]);
  if (!Number.isFinite(focusDistanceMm) || focusDistanceMm <= focalLengthMm) {
    throw new DofValidationError([{ field: "focusDistanceMm", code: "FOCUS_DISTANCE_NOT_GREATER_THAN_FOCAL_LENGTH" }]);
  }
  return (focalLengthMm ** 2 * Math.abs(objectDistanceMm - focusDistanceMm))
    / (fNumber * objectDistanceMm * (focusDistanceMm - focalLengthMm));
}

function calculateLimits(input) {
  const { focalLengthMm: f, fNumber: n, focusDistanceMm: s } = input;
  const c = input.criterion.valueMm;
  const nearMm = (s * f ** 2) / (f ** 2 + n * c * (s - f));
  const farDenominator = f ** 2 - n * c * (s - f);
  const farIsInfinite = farDenominator <= 0;
  return {
    nearMm,
    farMm: farIsInfinite ? null : (s * f ** 2) / farDenominator,
    farIsInfinite,
    farDenominator,
  };
}

export function calculateNearLimitMm(input) {
  validateClassicInput(input);
  return calculateLimits(input).nearMm;
}

export function calculateFarLimit(input) {
  validateClassicInput(input);
  const { farMm, farIsInfinite } = calculateLimits(input);
  return { farMm, farIsInfinite };
}

export function calculateCriterionCrossings(input) {
  validateClassicInput(input);
  const limits = calculateLimits(input);
  return {
    nearMm: limits.nearMm,
    farMm: limits.farMm,
    farIsInfinite: limits.farIsInfinite,
  };
}

export function evaluateCriterionAtDistance(input, objectDistanceMm) {
  validateClassicInput(input);
  const blurMm = calculateGeometricBlurMm({
    objectDistanceMm,
    focalLengthMm: input.focalLengthMm,
    fNumber: input.fNumber,
    focusDistanceMm: input.focusDistanceMm,
  });
  const marginMm = input.criterion.valueMm - blurMm;
  return { objectDistanceMm, blurMm, criterionMm: input.criterion.valueMm, marginMm, criterionMet: marginMm >= 0 };
}

export function estimateThinLensMagnification(input) {
  validateClassicInput(input);
  return {
    value: input.focalLengthMm / (input.focusDistanceMm - input.focalLengthMm),
    evidenceState: "MODEL",
    modelId: GEOMETRIC_MODEL.id,
    realLensMagnificationState: "UNKNOWN",
  };
}

export function calculateClassicDof(input) {
  validateClassicInput(input);
  const limits = calculateLimits(input);
  const frontDofMm = input.focusDistanceMm - limits.nearMm;
  const rearDofMm = limits.farIsInfinite ? null : limits.farMm - input.focusDistanceMm;
  const totalDofMm = limits.farIsInfinite ? null : limits.farMm - limits.nearMm;
  const magnificationEstimate = estimateThinLensMagnification(input);
  const warnings = [];
  if (magnificationEstimate.value >= 0.1) {
    warnings.push({
      code: "CLOSE_FOCUS_MODEL_LIMIT",
      severity: "WARNING",
      threshold: 0.1,
      estimate: magnificationEstimate,
      evidenceState: "MODEL",
      provenanceId: "RP-2026-011",
    });
  }
  return {
    model: GEOMETRIC_MODEL,
    units: { length: "mm", fNumber: "dimensionless" },
    sensor: { ...input.sensor },
    criterion: { ...input.criterion },
    nearMm: limits.nearMm,
    focusDistanceMm: input.focusDistanceMm,
    farMm: limits.farMm,
    farIsInfinite: limits.farIsInfinite,
    frontDofMm,
    rearDofMm,
    totalDofMm,
    hyperfocalMm: calculateHyperfocalMm({
      focalLengthMm: input.focalLengthMm,
      fNumber: input.fNumber,
      criterionMm: input.criterion.valueMm,
    }),
    magnificationEstimate,
    crossings: {
      nearMm: limits.nearMm,
      farMm: limits.farMm,
      farIsInfinite: limits.farIsInfinite,
    },
    warnings,
  };
}

export function sampleContinuousCurve(input, options) {
  validateClassicInput(input);
  const { startObjectDistanceMm, endObjectDistanceMm, sampleCount } = options ?? {};
  if (!Number.isInteger(sampleCount) || sampleCount < 2) {
    throw new DofValidationError([{ field: "sampleCount", code: "INVALID_SAMPLE_COUNT" }]);
  }
  if (!isPositiveFinite(startObjectDistanceMm) || startObjectDistanceMm <= input.focalLengthMm) {
    throw new DofValidationError([{ field: "startObjectDistanceMm", code: "INVALID_CURVE_START" }]);
  }
  if (!isPositiveFinite(endObjectDistanceMm) || endObjectDistanceMm <= startObjectDistanceMm) {
    throw new DofValidationError([{ field: "endObjectDistanceMm", code: "INVALID_CURVE_END" }]);
  }
  const stepMm = (endObjectDistanceMm - startObjectDistanceMm) / (sampleCount - 1);
  const samples = Array.from({ length: sampleCount }, (_, index) =>
    evaluateCriterionAtDistance(input, startObjectDistanceMm + stepMm * index));
  return {
    strategy: "linear",
    requestedSampleCount: sampleCount,
    samples,
    crossings: calculateCriterionCrossings(input),
    units: { objectDistance: "mm", blur: "mm", criterionMargin: "mm" },
  };
}
