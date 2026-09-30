// Sidekick QR —— Card template（HD-SIDEKICKQR-002 / -003、AI-15970。Secondary QR は HD-SIDEKICKQR-007、AI-15975。URL / EXIF mode は HD-SIDEKICKQR-026、AI-15994）。
//
// 画像 ＋ タイトル ＋ 説明（任意）＋ QR ＋ branding → Card PNG。mode は 2 つ（Overlay / SNS は後続）:
//   * URL mode:  Primary QR = 利用者が入れた URL（direct、redirect しない）。Card の地 = 灰（STYLES.url）
//   * EXIF mode: Primary QR = EXIF Viewer の URL（https://www.sidekick-lab.com/exif#v=1&…、exif_reader.js の viewerUrl が作る、許可した項目だけ。
//                HD-SIDEKICKQR-028。plain text は iPhone で Web 検索へ渡るため使わない = HD-SIDEKICKQR-027）。Card の地 = 白（STYLES.exif）
//   * 画像: Image Adapter の `containedPhoto`（contain）を、Card の縁から MAT px 内側に置き、写真の周りに細線（frame）を 1 本
//   * Primary QR: QR encoder が作った PNG（ECC M・quiet zone 4 module・1 module = 10 px）。Card Engine が等倍・整数座標・補間なしで置く
//   * 文字: タイトル 1 行・説明 1 行（Card Engine が長い文字を「…」で省略）
//   * branding: Sidekick QR / by Sidekick Lab（HD-SIDEKICKQR-003）／ ← このカードを作る（矢印は左の Secondary QR を指す。1.1.0-rc.2、HD-SIDEKICKQR-028）
//   * Secondary QR: Sidekick QR の製品ページへの return 入口（PRODUCT_PAGE_URL、固定。mode に関係なく同じ）。branding の一部として左下に小さく（1 module = 5 px、quiet zone 4 module）。
//     Primary QR より必ず小さい（Card Engine が SECONDARY_QR_TOO_LARGE で拒否する）。QR にロゴ・文字を重ねない。
//   QR の quiet zone は QR の PNG が白で持つ。Card の地が灰でも QR の周りは白のまま（加工しない）。
// 由来: Generic Image Card prototype の `buildCard`（docs/PROVENANCE.md）。branding 以外は同じ組み立て。
"use strict";

(function (root) {
  // Secondary QR の行き先。Sidekick Lab site の恒久 URL。一時 URL・preview URL を入れない。
  // 1.0.1 から return 入口 /card/qr（HD-SIDEKICKQR-023。site が 307 で製品ページへ送る。小文字・末尾 / なし・query なし）。
  // 1.0.0 の Card に刻まれた /sidekick-qr（2026-09-27 本番公開、site commit b7dba20）はそのまま有効。
  const PRODUCT_PAGE_URL = "https://www.sidekick-lab.com/card/qr";
  const BRANDING = Object.freeze({ name: "Sidekick QR", caption: "by Sidekick Lab", cta: "← このカードを作る" });
  const QR_SCALE = 10;
  const QR_BORDER = 4;
  const SECONDARY_QR_SCALE = 5;
  const SECONDARY_QR_BORDER = 4;
  // Card の見た目（Sidekick シリーズの色: Planner Card = 黒、Sidekick QR URL = 灰、Sidekick QR EXIF = 白）。
  // 具体的な濃度・frame は Human Review で実物を見て決める（HD-SIDEKICKQR-026）。
  const STYLES = Object.freeze({
    url: Object.freeze({ background: "#e4e6e8", frame: "#aab1b7", rule: null }),
    exif: Object.freeze({ background: "#ffffff", frame: "#c7cdd2", rule: null }),
  });
  const MAT = 48;                // 写真の上・左・右の余白（px）。下は帯の余白（Card Engine の padding）が続く
  const FRAME_GAP = 12;          // 写真の縁と細線の間（px）
  const FRAME_WIDTH = 2;         // 細線の太さ（px）

  // Card の幅 → 写真の位置・大きさ・frame（Card Engine の `image(cardWidth)` の戻り値の形）
  function photoLayout(bitmap, cardWidth, style) {
    const inner = root.SidekickQrImage.containedPhoto(bitmap, cardWidth - 2 * MAT);
    const x = inner.x + MAT;
    const y = inner.y + MAT;
    const outset = FRAME_GAP + FRAME_WIDTH;
    return {
      source: inner.source, x, y, width: inner.width, height: inner.height, areaHeight: inner.areaHeight + MAT, areaFill: null,
      frame: { x: x - outset, y: y - outset, width: inner.width + 2 * outset, height: inner.height + 2 * outset,
               lineWidth: FRAME_WIDTH, color: style.frame },
    };
  }

  // {mode = "url", bitmap, title, description, href}。href = URL mode では利用者の URL、EXIF mode では EXIF Viewer の URL
  //   → {card: Blob(PNG), mode, payload, qrPng: Blob(PNG), qr, secondaryQrPng: Blob(PNG), secondaryQr}
  async function render({ mode = "url", bitmap, title, description, href }) {
    const style = STYLES[mode];
    if (!style) throw new Error("unknown card mode");
    const payload = href;
    if (typeof payload !== "string" || !payload) throw new Error("no QR payload");
    const qr = root.SidekickQr.encode(payload, { ecc: "M" });
    const qrPng = await root.SidekickQr.toPngBlob(qr, { scale: QR_SCALE, border: QR_BORDER });
    const secondaryQr = root.SidekickQr.encode(PRODUCT_PAGE_URL, { ecc: "M" });
    const secondaryQrPng = await root.SidekickQr.toPngBlob(secondaryQr, { scale: SECONDARY_QR_SCALE, border: SECONDARY_QR_BORDER });
    const card = await root.SidekickCardEngine.compose({
      qrPng,
      image: async (cardWidth) => photoLayout(bitmap, cardWidth, style),
      title,
      lines: description ? [["", description]] : [],
      branding: { ...BRANDING, qrPng: secondaryQrPng },
      style: { background: style.background, rule: style.rule },
    });
    return { card, mode, payload, qrPng, qr, secondaryQrPng, secondaryQr };
  }

  root.SidekickQrCard = Object.freeze({ render, photoLayout, BRANDING, PRODUCT_PAGE_URL, QR_SCALE, QR_BORDER, SECONDARY_QR_SCALE,
                                        SECONDARY_QR_BORDER, STYLES, MAT, FRAME_GAP, FRAME_WIDTH });
})(typeof window === "undefined" ? globalThis : window);
