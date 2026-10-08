// SharePlan fragment の受信と、Map 表示用の値の導出（G-2 §3）。
//
// 受信判定は share.html の受信口（viewer_decoder.generated.js、share.html から機械的に切り出した写し）を
// そのまま使う。server が足すのは次だけ:
//   - 文字数の上限（decode 前に大きすぎる入力を捨てる）
//   - zlib stream の後ろに余計な byte が無いこと（Python canonical の TRAILING_DATA と同じ。多重防御）
//   - 公開してよい version / genre の allow-list（HD-G0-009）
// 表示用の値（座標・日時・被写体名）は **fragment から server 自身が導く**。client が送る値は使わない。
"use strict";

const zlib = require("node:zlib");
const { CONSTANTS } = require("./config");
const { sha256Hex } = require("./tokens");
const viewer = require("./viewer_decoder.generated.js");
const { categoriesFromDecoded } = require("./discovery");

class SharePlanError extends Error {
  constructor(code, message) {
    super(message || code);
    this.code = code;
  }
}

function v2Labels(wire) {
  const V2 = viewer.SPEC.v2;
  const names = viewer.SPEC.viewer.poi_display_names;
  const genre = wire.g;
  let targetLabel = null;
  if (wire.r) {
    const known = Object.prototype.hasOwnProperty.call(names, wire.r.p) ? names[wire.r.p] : null;
    targetLabel = (typeof known === "string" && known) || wire.r.l || wire.r.p;
  }
  let skyObjectLabel = null;
  if (genre === "star_landscape" && wire.b && Object.prototype.hasOwnProperty.call(V2.sky_object_names, wire.b.o)) {
    skyObjectLabel = V2.sky_object_names[wire.b.o];
  }
  return { genreLabel: V2.genre_labels[genre] || genre, targetLabel, skyObjectLabel };
}

// fragment → { snapshot, display }。受理できなければ SharePlanError（code は share.html と同じ語彙）
async function parsePublishableFragment(fragment) {
  if (typeof fragment !== "string" || fragment === "") {
    throw new SharePlanError(viewer.CODES.EMPTY_FRAGMENT);
  }
  if (fragment.length > CONSTANTS.MAX_FRAGMENT_CHARS) {
    throw new SharePlanError(viewer.CODES.PAYLOAD_TOO_LARGE);
  }
  let decoded;
  try {
    decoded = await viewer.decodeFragment(fragment);
  } catch (error) {
    const code = error && typeof error.code === "string" ? error.code : "NOT_SIDEKICK_QR";
    throw new SharePlanError(code);
  }
  // 多重防御: zlib stream の終わりで入力が尽きていること（Node の DecompressionStream も拒否するが明示する）
  const raw = Buffer.from(fragment, "base64url");
  const inflated = zlib.inflateSync(raw, { info: true, maxOutputLength: viewer.SPEC.decompressed_max });
  if (inflated.engine.bytesWritten !== raw.length) {
    throw new SharePlanError(viewer.CODES.TRAILING_DATA);
  }

  const version = decoded.share_format_version;
  const genre = decoded.plan_genre;
  const allowed = CONSTANTS.ALLOWED_GENRES[version];
  if (!allowed) throw new SharePlanError(viewer.CODES.UNSUPPORTED_VERSION);
  if (!allowed.includes(genre)) throw new SharePlanError(viewer.CODES.UNSUPPORTED_GENRE);

  let display;
  if (version === 1) {
    display = {
      lat: decoded.observer_latitude_deg,
      lon: decoded.observer_longitude_deg,
      t_d: decoded.utc_datetime,
      genre,
      genre_label: viewer.planTitle(decoded),
      target_label: viewer.subjectName(decoded),
      sky_object_label: null
    };
  } else {
    const wire = decoded.wire;
    const labels = v2Labels(wire);
    display = {
      lat: wire.o.x,
      lon: wire.o.y,
      t_d: wire.t.d,
      genre,
      genre_label: labels.genreLabel,
      target_label: labels.targetLabel,
      sky_object_label: labels.skyObjectLabel
    };
  }
  // G-6（Map Discovery Filter）: Map で探すための分類層。genre・空の対象 id から導く（表示文字列では判定しない）
  display.categories = categoriesFromDecoded(decoded);
  return {
    snapshot: {
      fragment,
      payload_sha256: sha256Hex(fragment), // fingerprint であって identity ではない（HD-G0-005）
      share_version: version,
      genre
    },
    display
  };
}

module.exports = { SharePlanError, parsePublishableFragment, VIEWER_SOURCE_SHA256: viewer.SOURCE_SHA256 };
