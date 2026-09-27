// Sidekick QR —— Card template（HD-SIDEKICKQR-002 / -003、AI-15970。Secondary QR は HD-SIDEKICKQR-007、AI-15975）。
//
// 画像 ＋ タイトル ＋ 説明（任意）＋ QR ＋ branding → Card PNG。今の MVP の template はこれ 1 種類（Overlay / SNS は後続）。
//   * 画像: Image Adapter の `containedPhoto`（contain）
//   * Primary QR:   利用者が入れた URL。QR encoder が作った PNG（ECC M・quiet zone 4 module・1 module = 10 px）。Card Engine が等倍・整数座標・補間なしで置く
//   * 文字: タイトル 1 行・説明 1 行（Card Engine が長い文字を「…」で省略）
//   * branding: Sidekick QR / by Sidekick Lab（HD-SIDEKICKQR-003）／ このカードを作る →
//   * Secondary QR: Sidekick QR の製品ページ（PRODUCT_PAGE_URL、固定）。branding の一部として左下に小さく（1 module = 5 px、quiet zone 4 module）。
//     Primary QR より必ず小さい（Card Engine が SECONDARY_QR_TOO_LARGE で拒否する）。QR にロゴ・文字を重ねない。
// 由来: Generic Image Card prototype の `buildCard`（docs/PROVENANCE.md）。branding 以外は同じ組み立て。
"use strict";

(function (root) {
  // Secondary QR の行き先。Sidekick Lab site の恒久 URL（2026-09-27 本番公開、site commit b7dba20）。一時 URL・preview URL を入れない。
  const PRODUCT_PAGE_URL = "https://www.sidekick-lab.com/sidekick-qr";
  const BRANDING = Object.freeze({ name: "Sidekick QR", caption: "by Sidekick Lab", cta: "このカードを作る →" });
  const QR_SCALE = 10;
  const QR_BORDER = 4;
  const SECONDARY_QR_SCALE = 5;
  const SECONDARY_QR_BORDER = 4;

  // {bitmap, title, description, href} → {card: Blob(PNG), qrPng: Blob(PNG), qr, secondaryQrPng: Blob(PNG), secondaryQr}
  async function render({ bitmap, title, description, href }) {
    const qr = root.SidekickQr.encode(href, { ecc: "M" });
    const qrPng = await root.SidekickQr.toPngBlob(qr, { scale: QR_SCALE, border: QR_BORDER });
    const secondaryQr = root.SidekickQr.encode(PRODUCT_PAGE_URL, { ecc: "M" });
    const secondaryQrPng = await root.SidekickQr.toPngBlob(secondaryQr, { scale: SECONDARY_QR_SCALE, border: SECONDARY_QR_BORDER });
    const card = await root.SidekickCardEngine.compose({
      qrPng,
      image: async (cardWidth) => root.SidekickQrImage.containedPhoto(bitmap, cardWidth),
      title,
      lines: description ? [["", description]] : [],
      branding: { ...BRANDING, qrPng: secondaryQrPng },
    });
    return { card, qrPng, qr, secondaryQrPng, secondaryQr };
  }

  root.SidekickQrCard = Object.freeze({ render, BRANDING, PRODUCT_PAGE_URL, QR_SCALE, QR_BORDER, SECONDARY_QR_SCALE,
                                        SECONDARY_QR_BORDER });
})(typeof window === "undefined" ? globalThis : window);
