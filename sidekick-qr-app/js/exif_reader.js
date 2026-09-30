// Sidekick QR —— EXIF の撮影情報（EXIF mode、HD-SIDEKICKQR-026、AI-15994。Primary = EXIF Viewer の URL は HD-SIDEKICKQR-028、AI-15995）。
//
// 利用者が EXIF mode を選んだときだけ、写真の file から **許可した撮影情報だけ** を取り出し、Primary QR に入れる URL と画面の表示を作る。
//   1. extract: file の bytes → EXIF data model（言語に依存しない値。下の FIELDS の 7 項目だけ）
//   2. serializer: data model → 画面に出す human-readable text（1.1.0 は日本語だけ、SERIALIZERS.ja。英語等は将来ここに足す）
//   3. viewerUrl: data model → Primary QR の URL（https://www.sidekick-lab.com/exif#v=1&…）。plain text の QR は iPhone で Web 検索へ渡るため
//      使わない（HD-SIDEKICKQR-027）。Viewer は 2. と同じ日本語表現で表示する
//
// **allow-list 方式**。読む tag は IFD0 の Make / Model / Exif IFD pointer と、Exif IFD の 7 種類（下の TAG）だけ。
// GPS IFD（0x8825）・Interoperability IFD・IFD1（thumbnail）・MakerNote（0x927C）は **辿らない / 読まない**。
// serial number・Artist・Copyright・UserComment・ImageUniqueID 等は tag を参照しないので、data model に入る経路がない。
// 値が無い・0・範囲外・壊れている項目は data model に入れない（serializer はその行を出さない）。
// 文字の項目は制御文字・不可視の書式文字を除き、MAX_TEXT 文字までにする。
//
// **privacy 境界**: 通信しない（この file は fetch / XHR / beacon / WebSocket を使わない）。写真・EXIF・text を外へ送らない・記録しない。
// 保存 Card の PNG へ EXIF を写さない（Card は canvas から作り直す。この file は QR に入れる URL と表示の text を作るだけ）。
// 依存なし（ブラウザ標準の ArrayBuffer / DataView / TextDecoder だけ）。
"use strict";

(function (root) {
  const MAX_TEXT = 64;                                   // 文字の項目（カメラ・レンズ）の上限（code point）
  const MAX_ENTRIES = 1000;                              // 1 つの IFD の entry 数の上限（壊れた file で回り続けない）
  const TAG = Object.freeze({
    make: 0x010F, model: 0x0110, exifIfd: 0x8769,        // IFD0
    exposureTime: 0x829A, fNumber: 0x829D, iso: 0x8827, isoSpeed: 0x8833,
    dateTimeOriginal: 0x9003, dateTimeDigitized: 0x9004, focalLength: 0x920A, lensModel: 0xA434,   // Exif IFD
  });
  // data model の項目（この順で serializer が並べる）
  const FIELDS = Object.freeze(["camera", "lens", "focalLength", "aperture", "exposureTime", "iso", "dateTime"]);
  const TYPE_SIZE = { 1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 7: 1, 9: 4, 10: 8, 13: 4, 129: 1 };

  // ---- 1. bytes → TIFF（EXIF 本体）の範囲 ----------------------------------------------------
  // JPEG: APP1 の「Exif\0\0」segment（最初の 1 つ）。PNG: eXIf chunk。どちらも無ければ null。
  function tiffOf(bytes) {
    const n = bytes.length;
    if (n >= 4 && bytes[0] === 0xFF && bytes[1] === 0xD8) {
      let pos = 2;
      while (pos + 4 <= n) {
        if (bytes[pos] !== 0xFF) return null;
        const marker = bytes[pos + 1];
        if (marker === 0xFF) { pos += 1; continue; }
        if (marker === 0x01 || (marker >= 0xD0 && marker <= 0xD7)) { pos += 2; continue; }
        if (marker === 0xDA || marker === 0xD9) return null;        // 画像 data に入った = EXIF は無い
        const length = (bytes[pos + 2] << 8) | bytes[pos + 3];
        if (length < 2 || pos + 2 + length > n) return null;
        if (marker === 0xE1 && length >= 8 && bytes[pos + 4] === 0x45 && bytes[pos + 5] === 0x78 && bytes[pos + 6] === 0x69
            && bytes[pos + 7] === 0x66 && bytes[pos + 8] === 0 && bytes[pos + 9] === 0) {
          return bytes.subarray(pos + 10, pos + 2 + length);
        }
        pos += 2 + length;
      }
      return null;
    }
    const PNG = [0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A];
    if (n >= 8 && PNG.every((b, i) => bytes[i] === b)) {
      let pos = 8;
      while (pos + 12 <= n) {
        const length = ((bytes[pos] << 24) >>> 0) + (bytes[pos + 1] << 16) + (bytes[pos + 2] << 8) + bytes[pos + 3];
        const type = String.fromCharCode(bytes[pos + 4], bytes[pos + 5], bytes[pos + 6], bytes[pos + 7]);
        if (pos + 12 + length > n) return null;
        if (type === "eXIf") return bytes.subarray(pos + 8, pos + 8 + length);
        if (type === "IEND") return null;
        pos += 12 + length;
      }
    }
    return null;
  }

  // ---- 2. TIFF → 許可した tag の生の値 -------------------------------------------------------
  function readTiff(tiff) {
    if (tiff.length < 8) return {};
    const view = new DataView(tiff.buffer, tiff.byteOffset, tiff.byteLength);
    const order = String.fromCharCode(tiff[0], tiff[1]);
    if (order !== "II" && order !== "MM") return {};
    const le = order === "II";
    if (view.getUint16(2, le) !== 42) return {};

    // IFD の entry のうち `wanted` の tag だけを {tag: {type, count, at}} で返す（at = 値の位置。範囲外なら入れない）
    const ifd = (offset, wanted) => {
      const found = {};
      if (offset < 8 || offset + 2 > tiff.length) return found;
      const count = view.getUint16(offset, le);
      if (count > MAX_ENTRIES || offset + 2 + count * 12 > tiff.length) return found;
      for (let i = 0; i < count; i += 1) {
        const entry = offset + 2 + i * 12;
        const tag = view.getUint16(entry, le);
        if (!wanted.has(tag) || found[tag]) continue;
        const type = view.getUint16(entry + 2, le);
        const items = view.getUint32(entry + 4, le);
        const size = TYPE_SIZE[type];
        if (!size || items === 0 || items > 65536) continue;
        const bytes = size * items;
        const at = bytes <= 4 ? entry + 8 : view.getUint32(entry + 8, le);
        if (at + bytes > tiff.length) continue;
        found[tag] = { type, count: items, at };
      }
      return found;
    };
    const text = (e) => {
      if (!e || (e.type !== 2 && e.type !== 129)) return null;
      let raw = tiff.subarray(e.at, e.at + e.count);
      const end = raw.indexOf(0);
      if (end >= 0) raw = raw.subarray(0, end);
      try { return new TextDecoder("utf-8", { fatal: true }).decode(raw); } catch (_) { return null; }  // 壊れた文字 = 無し
    };
    const rational = (e) => {
      if (!e || (e.type !== 5 && e.type !== 10)) return null;
      const num = e.type === 5 ? view.getUint32(e.at, le) : view.getInt32(e.at, le);
      const den = e.type === 5 ? view.getUint32(e.at + 4, le) : view.getInt32(e.at + 4, le);
      return den > 0 && num > 0 ? { num, den } : null;
    };
    const integer = (e) => {
      if (!e) return null;
      if (e.type === 3) return view.getUint16(e.at, le);
      if (e.type === 4) return view.getUint32(e.at, le);
      return null;
    };

    const ifd0 = ifd(view.getUint32(4, le), new Set([TAG.make, TAG.model, TAG.exifIfd]));
    const pointer = ifd0[TAG.exifIfd];
    const exifOffset = pointer && (pointer.type === 4 || pointer.type === 13) && pointer.count === 1 ? view.getUint32(pointer.at, le) : 0;
    const exif = ifd(exifOffset, new Set([TAG.exposureTime, TAG.fNumber, TAG.iso, TAG.isoSpeed, TAG.dateTimeOriginal,
                                           TAG.dateTimeDigitized, TAG.focalLength, TAG.lensModel]));
    return {
      make: text(ifd0[TAG.make]), model: text(ifd0[TAG.model]), lensModel: text(exif[TAG.lensModel]),
      focalLength: rational(exif[TAG.focalLength]), fNumber: rational(exif[TAG.fNumber]), exposureTime: rational(exif[TAG.exposureTime]),
      iso: integer(exif[TAG.iso]), isoSpeed: integer(exif[TAG.isoSpeed]),
      dateTimeOriginal: text(exif[TAG.dateTimeOriginal]), dateTimeDigitized: text(exif[TAG.dateTimeDigitized]),
    };
  }

  // ---- 3. 生の値 → data model（検証・安全処理。言語に依存しない） -------------------------------
  // 制御文字（C0 / DEL / C1）と、表示を乱す不可視の書式文字（zero-width・bidi の制御・BOM）を除き、空白をまとめ、MAX_TEXT 文字までにする
  function cleanText(value) {
    if (typeof value !== "string") return null;
    const cleaned = value.replace(/[\u0000-\u001f\u007f-\u009f\u200b-\u200f\u2028-\u202e\u2060-\u2069\ufeff]/g, " ")
      .replace(/\s+/g, " ").trim();
    if (!cleaned) return null;
    const chars = Array.from(cleaned);
    return chars.length <= MAX_TEXT ? cleaned : chars.slice(0, MAX_TEXT - 1).join("").trimEnd() + "…";
  }

  function ratio(r, min, max) {
    if (!r) return null;
    const value = r.num / r.den;
    return Number.isFinite(value) && value > min && value <= max ? value : null;
  }

  function dateTime(value) {
    const m = typeof value === "string" && value.trim().match(/^(\d{4}):(\d{2}):(\d{2})[ T](\d{2}):(\d{2})(?::(\d{2}))?/);
    if (!m) return null;
    const [year, month, day, hour, minute] = m.slice(1, 6).map(Number);
    if (year < 1900 || year > 2999 || month < 1 || month > 12 || day < 1 || day > 31 || hour > 23 || minute > 59) return null;
    return { year, month, day, hour, minute };                 // timezone は持たない（推測・付加しない）
  }

  function isoOf(raw) {
    const valid = (v) => Number.isInteger(v) && v > 0 && v < 10000000;
    if (valid(raw.iso) && raw.iso !== 65535) return raw.iso;  // 65535 = 「65535 以上」の印。正確な値は ISOSpeed を見る
    return valid(raw.isoSpeed) ? raw.isoSpeed : null;
  }

  // bytes（ArrayBuffer / Uint8Array）→ data model {camera, lens, focalLength, aperture, exposureTime, iso, dateTime}（無い項目は null）
  function extract(data) {
    const model = { camera: null, lens: null, focalLength: null, aperture: null, exposureTime: null, iso: null, dateTime: null };
    let raw = {};
    try {
      const bytes = data instanceof Uint8Array ? data : new Uint8Array(data);
      const tiff = tiffOf(bytes);
      raw = tiff ? readTiff(tiff) : {};
    } catch (_) {
      raw = {};                                                // 壊れた EXIF = 撮影情報なし
    }
    model.camera = cleanText(raw.model) || cleanText(raw.make);
    model.lens = cleanText(raw.lensModel);
    model.focalLength = ratio(raw.focalLength, 0, 10000);                                  // mm
    model.aperture = ratio(raw.fNumber, 0, 1000);                                          // F 値
    model.exposureTime = ratio(raw.exposureTime, 0, 100000) ? raw.exposureTime : null;     // 秒（分数のまま）
    model.iso = isoOf(raw);
    model.dateTime = dateTime(raw.dateTimeOriginal) || dateTime(raw.dateTimeDigitized);
    return model;
  }

  async function readFile(file) {
    return extract(await file.arrayBuffer());
  }

  function isEmpty(model) {
    return !model || FIELDS.every((field) => model[field] === null || model[field] === undefined);
  }

  // ---- 4. serializer（QR に入れる human-readable text） ------------------------------------
  const decimal = (value) => String(Math.round(value * 10) / 10);            // 11 / 2.8 / 18.5
  const pad2 = (value) => String(value).padStart(2, "0");

  // シャッター速度の値（単位なし）: 1 秒以上は秒の数値（60 / 2.5）、1 秒未満は自然な分数（1/750）か秒の数値（0.4）
  function shutterValue({ num, den }) {
    const seconds = num / den;
    if (seconds >= 1) return decimal(seconds);
    const inverse = den / num;
    if (Number.isInteger(inverse)) return "1/" + inverse;
    const nearest = Math.round(inverse);
    if (nearest >= 2 && Math.abs(inverse - nearest) / inverse < 0.03) return "1/" + nearest;
    return seconds >= 0.1 ? decimal(seconds) : "1/" + nearest;
  }
  const shutter = (value) => shutterValue(value) + " s";                      // 1/750 s / 60 s / 0.4 s

  // Sidekick QR 1.1.0 の日本語 human-readable EXIF 表現（HD-SIDEKICKQR-026）。machine interchange format ではない。
  const SERIALIZERS = Object.freeze({
    ja: Object.freeze({
      labels: Object.freeze({ camera: "カメラ", lens: "レンズ", focalLength: "焦点距離", aperture: "絞り", exposureTime: "シャッター速度",
                              iso: "ISO", dateTime: "撮影日時" }),
      format: Object.freeze({
        camera: (v) => v, lens: (v) => v,
        focalLength: (v) => decimal(v) + " mm",
        aperture: (v) => "f/" + decimal(v),
        exposureTime: shutter,
        iso: (v) => String(v),
        dateTime: (v) => v.year + "-" + pad2(v.month) + "-" + pad2(v.day) + " " + pad2(v.hour) + ":" + pad2(v.minute),
      }),
    }),
  });

  // data model → text（有効な項目だけ、FIELDS の順、1 行 1 項目。何も無ければ ""）
  function serialize(model, language = "ja") {
    const serializer = SERIALIZERS[language];
    if (!serializer) throw new Error("unknown language");
    if (isEmpty(model)) return "";
    return FIELDS.filter((field) => model[field] !== null && model[field] !== undefined)
      .map((field) => serializer.labels[field] + ": " + serializer.format[field](model[field]))
      .join("\n");
  }

  // ---- 5. Primary QR の URL（EXIF Viewer v1、HD-SIDEKICKQR-028）-------------------------------------
  // https://www.sidekick-lab.com/exif#v=1&c=…&l=…&f=…&a=…&s=…&i=…&t=… —— 撮影情報は fragment（# の後）だけに入る（HTTP の request に含まれない）。
  // key と値の形は Viewer の decoder contract v=1（docs/EXIF_VIEWER_V1.md）。圧縮しない（URL を見ればある程度読める）。encode は URLSearchParams。
  const VIEWER_URL = "https://www.sidekick-lab.com/exif";
  const VIEWER_KEYS = Object.freeze({ camera: "c", lens: "l", focalLength: "f", aperture: "a", exposureTime: "s", iso: "i", dateTime: "t" });
  const VIEWER_FORMAT = Object.freeze({
    camera: (v) => v, lens: (v) => v,
    focalLength: (v) => decimal(v),
    aperture: (v) => decimal(v),
    exposureTime: shutterValue,
    iso: (v) => String(v),
    dateTime: (v) => String(v.year) + pad2(v.month) + pad2(v.day) + pad2(v.hour) + pad2(v.minute),   // YYYYMMDDHHMM、timezone なし
  });

  // data model → Viewer の URL（有効な項目だけ、FIELDS の順。何も無ければ ""）
  function viewerUrl(model) {
    if (isEmpty(model)) return "";
    const params = new URLSearchParams([["v", "1"]]);
    for (const field of FIELDS) {
      if (model[field] !== null && model[field] !== undefined) params.append(VIEWER_KEYS[field], VIEWER_FORMAT[field](model[field]));
    }
    return VIEWER_URL + "#" + params.toString();
  }

  root.SidekickQrExif = Object.freeze({ extract, readFile, serialize, viewerUrl, isEmpty, FIELDS, SERIALIZERS, MAX_TEXT, TAG, VIEWER_URL,
                                        VIEWER_KEYS });
})(typeof window === "undefined" ? globalThis : window);
