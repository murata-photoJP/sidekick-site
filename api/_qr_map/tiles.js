// 有限範囲の取得（HD-G0-007）: Web Mercator の data tile（z/x/y）。
//
// 各 PublicPlan は公開時に、決まった段（CONSTANTS.TILE_LEVELS）の tile key を 1 つずつ持つ
// （例: tiles.z10 = "10/909/403"）。Map は表示 zoom に応じて段を選び、画面を覆う data tile を
// 1 枚ずつ取りに来る。1 tile の問い合わせは「state == published かつ tile key 一致 かつ expires_at > now」
// の 1 query で、上限件数で打ち切る（全件取得の経路を作らない）。
// tile key は表示上の区分けであって PublicPlan の identity ではない。
"use strict";

const { CONSTANTS } = require("./config");

const MAX_LAT = 85.05112878;

function tileXY(lat, lon, z) {
  const clampedLat = Math.max(-MAX_LAT, Math.min(MAX_LAT, lat));
  const n = 2 ** z;
  const rad = (clampedLat * Math.PI) / 180;
  let x = Math.floor(((lon + 180) / 360) * n);
  let y = Math.floor(((1 - Math.log(Math.tan(rad) + 1 / Math.cos(rad)) / Math.PI) / 2) * n);
  x = Math.min(n - 1, Math.max(0, x));
  y = Math.min(n - 1, Math.max(0, y));
  return { x, y };
}

function tileKey(z, x, y) {
  return z + "/" + x + "/" + y;
}

// 公開時に保存する tile key の組（段ごとに 1 つ）
function tileKeysFor(lat, lon) {
  const keys = {};
  for (const z of CONSTANTS.TILE_LEVELS) {
    const { x, y } = tileXY(lat, lon, z);
    keys["z" + z] = tileKey(z, x, y);
  }
  return keys;
}

// 要求された tile を検証する。受けるのは TILE_LEVELS の段だけ、x / y は範囲内の整数だけ
function parseTileRequest(zRaw, xRaw, yRaw) {
  const toInt = (v) => (typeof v === "string" && /^[0-9]{1,6}$/.test(v) ? Number(v) : NaN);
  const z = toInt(zRaw);
  const x = toInt(xRaw);
  const y = toInt(yRaw);
  if (!CONSTANTS.TILE_LEVELS.includes(z)) return null;
  const n = 2 ** z;
  if (!Number.isInteger(x) || !Number.isInteger(y) || x >= n || y >= n) return null;
  return { z, x, y, field: "tiles.z" + z, key: tileKey(z, x, y) };
}

module.exports = { tileXY, tileKey, tileKeysFor, parseTileRequest };
