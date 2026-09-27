// Sidekick QR —— Web 版だけの「保存・共有」adapter（HD-SIDEKICKQR-020、AI-15988）。Portable 1.0.0 には入らない。
//
// iPhone 等で［PNGとして保存］が「sidekick-qr-card.png PNG 画像」の file 表示になり分かりにくい（Human Review 2026-09-28）ため、
// **対応する端末だけ**、生成済みの Card PNG を OS の共有シート（navigator.share）へ渡す。それ以外は今の Download のまま（progressive enhancement）。
//
// * 判定は feature detection: `navigator.canShare({files: [PNG の File]})` が true、かつ主な入力が touch（`pointer: coarse`）。
//   PC（Windows の Chrome / Edge も file の共有に対応する）は、Human Review で PASS した Download をそのまま使う。
// * Card の bytes は作り直さない: app.js が `URL.createObjectURL(card)` で作った Blob をそのまま覚えておき、同じ Blob から File を作って渡す
//   （app の CSP `connect-src 'none'` のため blob: URL を fetch では読めない）。
// * Card Engine / QR / 画像処理 / URL policy / app.js は変えない。この file は保存ボタンの click を先に受け取るだけ。
// * 通信しない・記録しない（共有先・file 名・URL 等をどこにも送らない）。共有シートで利用者が選んだ先での処理は OS / その app の動作。
// * 共有シートを閉じた（AbortError）ときは何も表示しない。本当の失敗のときは Download に切り替える。
"use strict";

(function (root) {
  const FILENAME = "sidekick-qr-card.png";
  const blobs = new Map();                                   // object URL → Blob（app.js が作った Card の Blob を覚える）
  const create = URL.createObjectURL.bind(URL);
  const revoke = URL.revokeObjectURL.bind(URL);
  URL.createObjectURL = function (object) {
    const url = create(object);
    if (object instanceof Blob) blobs.set(url, object);
    return url;
  };
  URL.revokeObjectURL = function (url) {
    blobs.delete(url);
    return revoke(url);
  };

  function shareFiles(files) {
    try {
      return typeof navigator.share === "function" && typeof navigator.canShare === "function" && navigator.canShare({ files });
    } catch (_) {
      return false;
    }
  }

  function touchPrimary() {
    return typeof root.matchMedia === "function" && root.matchMedia("(pointer: coarse)").matches;
  }

  const probe = typeof File === "function" ? [new File([new Uint8Array(0)], FILENAME, { type: "image/png" })] : null;
  const enabled = Boolean(probe) && shareFiles(probe) && touchPrimary();
  let bypass = false;                                        // 失敗したときの Download（app.js の保存処理）を 1 回だけ通す

  function start() {
    const button = document.getElementById("save-card");
    const image = document.getElementById("card-image");
    const status = document.getElementById("status");
    if (!button || !image) return;
    root.SidekickQrWebShare = Object.freeze({ enabled });
    if (!enabled) return;
    button.textContent = "PNGを保存・共有";
    const hint = document.createElement("p");
    hint.id = "share-hint";
    hint.className = "note";
    hint.textContent = "保存先や共有先を選べます（表示される選択肢は端末によって違います）。";
    button.insertAdjacentElement("afterend", hint);

    document.addEventListener("click", (event) => {
      if (event.target !== button || button.disabled) return;
      if (bypass) { bypass = false; return; }               // app.js の Download へそのまま渡す
      const blob = blobs.get(image.getAttribute("src"));
      if (!blob) return;                                    // Card が無い・分からない → app.js に任せる
      const file = new File([blob], FILENAME, { type: "image/png" });
      if (!shareFiles([file])) return;
      event.stopImmediatePropagation();
      event.preventDefault();
      navigator.share({ files: [file] }).catch((error) => {
        if (error && error.name === "AbortError") return;   // 利用者が共有シートを閉じた = 失敗ではない
        if (status) {
          status.classList.remove("error");
          status.textContent = "共有を開けなかったため、PNG をダウンロードします。";
        }
        bypass = true;
        button.click();
      });
    }, true);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
  else start();
})(typeof window === "undefined" ? globalThis : window);
