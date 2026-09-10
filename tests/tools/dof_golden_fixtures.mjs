export const PHASE_1_GOLDEN_FIXTURES = Object.freeze({
  VF01: { focalLengthMm: 24, fNumber: 8, focusDistanceMm: 3000, criterionMm: 0.030, nearMm: 1339.285714, farIsInfinite: true, frontDofMm: 1660.714286 },
  VF02: { focalLengthMm: 50, fNumber: 4, focusDistanceMm: 3000, criterionMm: 0.030, nearMm: 2627.890680, farMm: 3494.874185, totalDofMm: 866.983505 },
  VF03: { focalLengthMm: 85, fNumber: 2, focusDistanceMm: 2000, criterionMm: 0.030, nearMm: 1968.691672, farMm: 2032.320221, totalDofMm: 63.628549 },
  VF04: { focalLengthMm: 200, fNumber: 4, focusDistanceMm: 10000, criterionMm: 0.030, nearMm: 9714.396736, farMm: 10302.905419, totalDofMm: 588.508683 },
  VF05: { focalLengthMm: 24, fNumber: 8, criterionMm: 0.030, hyperfocalMm: 2424 },
  VF06: { focalLengthMm: 24, fNumber: 8, focusDistanceMm: 2424, criterionMm: 0.030, nearMm: 1212, farIsInfinite: true },
  VF07: { rule: "far_denominator_lte_zero", farIsInfinite: true },
  VF08: { focalLengthMm: 100, focusDistanceMm: 1100, modelMagnification: 0.1, warningCode: "CLOSE_FOCUS_MODEL_LIMIT" },
  VF09: { phase: 2, status: "DEFERRED", reason: "print viewing geometry is outside Phase 1 Unit 1" },
  VF10: { phase: 2, status: "DEFERRED", reason: "100 percent monitor geometry is outside Phase 1 Unit 1" },
  VF11: { rule: "focus_distance_lte_focal_length_is_invalid" },
  VF12: { sourceFixture: "VF02", rule: "curve_crossings_equal_closed_form_limits" },
});
