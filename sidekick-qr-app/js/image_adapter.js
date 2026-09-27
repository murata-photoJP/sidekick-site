// Sidekick QR —— Image Adapter（HD-SIDEKICKQR-002、AI-15970）。
//
// JPEG / PNG 1 枚 → 向きを補正した bitmap → Card の画像領域に **全体を収める（contain、crop しない）** 形。
// 由来: Generic Image Card prototype の `decodePhoto` / `containedPhoto`（docs/PROVENANCE.md）。判定・上限・計算式は移植元と同じ。
//
// * browser 内だけで decode する（server へ送らない）。`createImageBitmap(file, {imageOrientation: "from-image"})` で EXIF の向きを反映。
// * canvas に描き直すので、元写真の EXIF（撮影地点の GPS 等）は出力に入らない。
// * **色管理は未検証**（docs/VALIDATION_BACKLOG.md「Color Management Validation」）。入力写真の色を正確に保つとは言わない。
"use strict";

(function (root) {
  const ACCEPTED_TYPES = new Set(["image/jpeg", "image/png"]);
  const MAX_FILE_BYTES = 40 * 1000 * 1000;
  const MAX_PIXELS = 80 * 1000 * 1000;
  // 画像の枠の縦横比（高さ / 幅）。この範囲に収まる写真は枠いっぱい、外れる写真は余白付きで全体を収める。
  const AREA_RATIO_MIN = 9 / 21;
  const AREA_RATIO_MAX = 4 / 3;
  const AREA_FILL = "#eef0f2";

  class ImageInputError extends Error {
    constructor(message) {
      super(message);
      this.name = "ImageInputError";
    }
  }

  // file → 向きを補正した bitmap。使い終わったら呼び出し側が `close()` する。
  async function decodePhoto(file) {
    if (!file) throw new ImageInputError("画像を選んでください。");
    if (!ACCEPTED_TYPES.has(file.type)) throw new ImageInputError("選べる画像は JPEG / PNG だけです。");
    if (file.size > MAX_FILE_BYTES) throw new ImageInputError("画像のファイルが大きすぎます（40MB まで）。");
    let bitmap;
    try {
      bitmap = await createImageBitmap(file, { imageOrientation: "from-image" });
    } catch (_) {
      throw new ImageInputError("画像を読み込めませんでした。別の JPEG / PNG を選んでください。");
    }
    if (bitmap.width * bitmap.height > MAX_PIXELS) {
      bitmap.close();
      throw new ImageInputError("画像の画素数が大きすぎます（8,000 万画素まで）。");
    }
    return bitmap;
  }

  // Card の幅に合わせた画像の枠と、その中に全体を収める位置。縮小は高品質で 1 回だけ行い、Card Engine は等倍で置く
  // （Card Engine の `image(cardWidth)` の戻り値の形）。
  function containedPhoto(bitmap, cardWidth) {
    const ratio = bitmap.height / bitmap.width;
    const areaHeight = Math.round(cardWidth * Math.min(Math.max(ratio, AREA_RATIO_MIN), AREA_RATIO_MAX));
    const scale = Math.min(cardWidth / bitmap.width, areaHeight / bitmap.height);
    const width = Math.max(1, Math.round(bitmap.width * scale));
    const height = Math.max(1, Math.round(bitmap.height * scale));
    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    const context = canvas.getContext("2d");
    context.imageSmoothingEnabled = true;
    context.imageSmoothingQuality = "high";
    context.drawImage(bitmap, 0, 0, width, height);
    return {
      source: canvas, x: Math.round((cardWidth - width) / 2), y: Math.round((areaHeight - height) / 2),
      width, height, areaHeight, areaFill: width === cardWidth && height === areaHeight ? null : AREA_FILL,
    };
  }

  root.SidekickQrImage = Object.freeze({
    decodePhoto, containedPhoto, ImageInputError, AREA_FILL,
    LIMITS: Object.freeze({ maxFileBytes: MAX_FILE_BYTES, maxPixels: MAX_PIXELS, areaRatioMin: AREA_RATIO_MIN, areaRatioMax: AREA_RATIO_MAX }),
  });
})(typeof window === "undefined" ? globalThis : window);
