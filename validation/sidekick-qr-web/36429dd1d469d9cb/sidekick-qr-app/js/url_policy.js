// Sidekick QR —— URL Policy（HD-SIDEKICKQR-002、AI-15970）。
//
// 由来: Generic Image Card prototype の `checkUrl` / `isPrivateHost`（docs/PROVENANCE.md）。判定と文言は移植元と同じ。
// 依存: `qr_encoder.js`（`window.SidekickQr`。QR の容量と version の判定に使う）。
//
// 拒否: http / https 以外の scheme（javascript: / data: / file: 等）、形が壊れている URL、空、空白・改行・制御文字、QR に入らない長さ。
// 警告（利用者の判断で使える）: http（暗号化なし）、localhost / private network、ユーザー名・パスワード入り、QR が細かくなる長さ。
// URL はどこにも送らない（到達確認もしない）。短縮 URL service も使わない。
"use strict";

(function (root) {
  // QR が細かくなりすぎる目安（ECC M の version。25 = 117 module）。禁止ではなく警告だけ。
  const DENSE_QR_VERSION = 25;

  function isPrivateHost(hostname) {
    const host = hostname.replace(/^\[|\]$/g, "").toLowerCase();
    if (host === "localhost" || host.endsWith(".localhost") || host.endsWith(".local") || host === "::1") return true;
    const v4 = host.match(/^(\d+)\.(\d+)\.(\d+)\.(\d+)$/);
    if (v4) {
      const [a, b] = [Number(v4[1]), Number(v4[2])];
      return a === 10 || a === 127 || a === 0 || (a === 169 && b === 254) || (a === 172 && b >= 16 && b <= 31) || (a === 192 && b === 168);
    }
    return /^f[cd][0-9a-f]{2}:/.test(host) || /^fe80:/.test(host);
  }

  // text → {ok, href（QR に入る正規化済み URL）, errors, warnings, qrVersion}
  function checkUrl(raw) {
    const text = String(raw || "").trim();
    const result = { ok: false, href: null, errors: [], warnings: [], qrVersion: null };
    if (!text) { result.errors.push("リンク先URLを入力してください。"); return result; }
    if (/[\u0000-\u001f\u007f\s]/.test(text)) {
      result.errors.push("URLに空白・改行・制御文字は使えません。");
      return result;
    }
    let url;
    try { url = new URL(text); } catch (_) { url = null; }
    if (!url) { result.errors.push("URLの形が正しくありません（例: https://www.example.com/）。"); return result; }
    if (url.protocol !== "https:" && url.protocol !== "http:") {
      result.errors.push("使えるのは http:// または https:// で始まるURLだけです。");
      return result;
    }
    if (!url.hostname) { result.errors.push("URLにサイトの名前（ドメイン）がありません。"); return result; }
    const href = url.href;                               // 実際に QR に入る文字列（日本語は percent-encode、国際化ドメインは punycode）
    if (!/^[\x21-\x7e]+$/.test(href)) { result.errors.push("URLの形が正しくありません。"); return result; }
    let qr;
    try {
      qr = root.SidekickQr.encode(href, { ecc: "M" });
    } catch (error) {
      result.errors.push(error && error.code === "QR_CAPACITY_EXCEEDED"
        ? "URLが長すぎてQRコードに入りません（" + href.length + " 文字、上限 " + root.SidekickQr.MAX_BYTES_ECC_M + " 文字）。"
        : "このURLはQRコードにできません。");
      return result;
    }
    if (url.protocol === "http:") result.warnings.push("暗号化されていないURL（http://）です。");
    if (isPrivateHost(url.hostname)) result.warnings.push("この端末や社内ネットワーク向けのURLです。ほかの人の端末では開けない可能性があります。");
    if (url.username || url.password) result.warnings.push("URLにユーザー名・パスワードが含まれています。本当にこのURLでよいか確認してください。");
    if (qr.version >= DENSE_QR_VERSION) result.warnings.push("URLが長いのでQRコードが細かくなります。小さく印刷すると読み取りにくくなります。");
    result.ok = true;
    result.href = href;
    result.qrVersion = qr.version;
    return result;
  }

  root.SidekickQrUrlPolicy = Object.freeze({ checkUrl, isPrivateHost, DENSE_QR_VERSION });
})(typeof window === "undefined" ? globalThis : window);
