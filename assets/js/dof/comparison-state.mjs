const NUMBER_KEYS = new Set(["sensorWidth", "sensorHeight", "focalLength", "fNumber", "focusDistance", "customCriterion"]);

function normalize(key, value) {
  if (!NUMBER_KEYS.has(key)) return String(value ?? "");
  const text = String(value ?? "").trim();
  if (text === "") return "";
  const parsed = Number(text);
  return Number.isFinite(parsed) ? parsed : text;
}

export function createInputSnapshot(values) {
  return Object.fromEntries(Object.entries(values).map(([key, value]) => [key, normalize(key, value)]));
}

export function changedInputKeys(previous, current) {
  if (!previous) return [];
  return Object.keys(current).filter((key) => !Object.is(previous[key], current[key]));
}

export function advanceComparison(history, record) {
  return { previous: history?.current ?? null, current: record };
}

export function compareDistance(previousMm, currentMm) {
  if (previousMm === null && currentMm === null) return { kind: "unchanged" };
  if (previousMm !== null && currentMm === null) return { kind: "transition", text: "有限 → ∞", label: "有限から無限へ変化" };
  if (previousMm === null && currentMm !== null) return { kind: "transition", text: "∞ → 有限", label: "無限から有限へ変化" };
  const deltaMm = currentMm - previousMm;
  if (Math.abs(deltaMm) < 1e-9) return { kind: "unchanged" };
  return { kind: "delta", direction: deltaMm > 0 ? "increase" : "decrease", deltaMm };
}
