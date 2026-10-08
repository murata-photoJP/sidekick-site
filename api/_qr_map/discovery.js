// プランナーQRマップ G-6「Map Discovery Filter」: PublicPlan の discovery 分類（display.categories）。
//
// categories は **Map で「何を撮るか」を探すための分類層**であって、Planner 内部の genre（plan_genre）そのものではない
// （HD G-6 / HD-6）。1 つの PublicPlan は 0 個ではなく 1 個以上の分類を持つ（どれにも当たらなければ "other"）。
//   - 判定に使うのは fragment から server が導いた **識別子だけ**（genre、v2 の空の対象 id `b.o`）。
//     表示用の文字列（sky_object_label の「天の川」等）では判定しない（翻訳・表記の変更で壊れないように）。
//   - 分類を増やすときは DISCOVERY_CATEGORIES に 1 行足す（API・DB・index を作り直さない）。
//   - 分類の失敗で公開を止めない: 想定外の入力は "other" にする。
"use strict";

const zlib = require("node:zlib");

const OTHER = "other";

// 順序 = 判定と表示の順。match.genres: plan_genre の一覧、match.skyObjects（任意）: v2 の空の対象 id（wire.b.o）
const DISCOVERY_CATEGORIES = Object.freeze([
  Object.freeze({ id: "diamond", match: Object.freeze({ genres: Object.freeze(["diamond_fuji"]) }) }),
  Object.freeze({ id: "pearl", match: Object.freeze({ genres: Object.freeze(["pearl_fuji"]) }) }),
  Object.freeze({ id: "milky_way", match: Object.freeze({ genres: Object.freeze(["star_landscape"]), skyObjects: Object.freeze(["milky_way"]) }) })
]);

const CATEGORY_ID_RE = /^[a-z][a-z0-9_]{0,31}$/;

// { genre, skyObject }（skyObject は v2 の wire.b.o、無ければ null）→ ["diamond"] など。必ず 1 個以上を返す
function categoriesFor({ genre, skyObject = null }) {
  const out = [];
  for (const c of DISCOVERY_CATEGORIES) {
    if (!c.match.genres.includes(genre)) continue;
    if (c.match.skyObjects && !c.match.skyObjects.includes(skyObject)) continue;
    out.push(c.id);
  }
  return out.length ? out : [OTHER];
}

// 受信済み（parsePublishableFragment で検証済み）の decoded から分類を導く
function categoriesFromDecoded(decoded) {
  try {
    if (decoded.share_format_version === 1) return categoriesFor({ genre: decoded.plan_genre });
    const wire = decoded.wire || {};
    const sky = wire.b && typeof wire.b.o === "string" ? wire.b.o : null;
    return categoriesFor({ genre: wire.g, skyObject: sky });
  } catch (_) {
    return [OTHER];
  }
}

// 保存済み document の分類。G-6 より前の document（display.categories が無い）は取得時に導く（migration しない、HD-6）。
// 保存済みの fragment は公開時に検証済みなので、空の対象 id だけを同期的に読む（表示文字列は使わない）。
function categoriesOfDocument(doc) {
  const stored = doc && doc.display && doc.display.categories;
  if (Array.isArray(stored) && stored.length && stored.every((c) => typeof c === "string" && CATEGORY_ID_RE.test(c))) {
    return stored.slice();
  }
  try {
    const genre = doc.display.genre;
    let sky = null;
    if (doc.snapshot && doc.snapshot.share_version === 2 && typeof doc.snapshot.fragment === "string") {
      const wire = JSON.parse(zlib.inflateSync(Buffer.from(doc.snapshot.fragment, "base64url"), { maxOutputLength: 64 * 1024 }).toString("utf8"));
      sky = wire && wire.b && typeof wire.b.o === "string" ? wire.b.o : null;
    }
    return categoriesFor({ genre, skyObject: sky });
  } catch (_) {
    return [OTHER];
  }
}

module.exports = { DISCOVERY_CATEGORIES, OTHER, categoriesFor, categoriesFromDecoded, categoriesOfDocument };
