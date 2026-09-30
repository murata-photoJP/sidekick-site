// Common Card Engine —— 上に画像、下に文字と QR を置いた 1 枚の PNG を作る（HD-PLANNERSHAREV2-GIC-001、AI-15962）。
//
// 2026-09-27: Planner の Technical Card（`share_card.js`、HD-PLANNERSHAREV2-004）から、**画像の出所に依存しない部分だけ**を
// そのまま切り出した。呼び出し側（Adapter）が決めるもの / この file が決めるもの:
//
//   Adapter:  上段に描く画像（Planner = 構図図、Generic = 利用者の写真）・その収め方、見出し・行・branding の文言、QR の PNG
//   Engine:   Card の幅と余白・区切り線・QR の配置（**等倍・整数座標・補間なし**、周りは白）・文字の省略・PNG 化
//
// この file は撮影計画（SharePlan / genre / 時刻 / target / `#preview-svg` / snapshot）も、Generic 固有の入力（file / URL 検証 / QR 生成）も知らない。
// **Planner Card の出力 bytes を変えない**ため、描画の順序・座標・文字の書式は切り出し前と同一に保つ（golden: `test_share_card_engine_golden_browser`）。
//
// 依存なし（ブラウザ標準の Image / canvas だけ）。外部 resource を読まない。
"use strict";

(function (root) {
  const CARD = Object.freeze({
    minWidth: 1600,          // Card の最小幅（px）
    padding: 48,             // 帯の余白（px）
    textMinWidth: 760,       // 情報欄の最小幅（px）
    background: "#ffffff",
    ink: "#1d2328",
    subInk: "#59636c",
    rule: "#c7cdd2",
  });

  class CardEngineError extends Error {
    constructor(code, message) {
      super(message);
      this.code = code;
    }
  }

  function loadImage(url) {
    return new Promise((resolve, reject) => {
      const image = new Image();
      image.onload = () => resolve(image);
      image.onerror = () => reject(new CardEngineError("IMAGE_LOAD_FAILED", "an image could not be decoded"));
      image.src = url;
    });
  }

  async function withObjectUrl(blob, use) {
    const url = URL.createObjectURL(blob);
    try {
      return await use(url);
    } finally {
      URL.revokeObjectURL(url);
    }
  }

  // QR の PNG から Card の幅を決める（QR の横に情報欄の最小幅が取れること）。
  function cardWidthFor(qrWidth) {
    return Math.max(CARD.minWidth, qrWidth + 3 * CARD.padding + CARD.textMinWidth);
  }

  function drawText(context, text, x, y, font, color, maxWidth) {
    context.font = font;
    context.fillStyle = color;
    context.textBaseline = "top";
    let value = String(text);
    while (value.length > 1 && context.measureText(value).width > maxWidth) value = value.slice(0, -2) + "…";
    context.fillText(value, x, y);
  }

  // input:
  //   qrPng:   Blob（QR の PNG。**加工しない**。等倍・整数座標・補間なしで置く）
  //   image:   async (cardWidth) => ({source, x, y, width, height, areaHeight, areaFill?})
  //            上段の画像領域（高さ areaHeight）に source を (x, y, width, height) で描く。areaFill があれば先に領域をその色で塗る（contain の余白）。
  //   title:   見出し 1 行
  //   lines:   [[label, value], ...]（label が空なら値だけの行）
  //            frame（任意、2026-09-30 追加）: {x, y, width, height, lineWidth, color} があれば、写真の周りにその矩形の細線を描く（Sidekick QR 1.1.0 の mat / frame）。
  //   style（任意、2026-09-30 追加）: {background, rule}。Card の地の色と、写真と帯の区切り線（rule が null なら描かない）。無ければ今までの CARD の値。
  //            QR の quiet zone は QR の PNG 自体が白で持っているので、地の色を変えても白のまま（QR の PNG は加工しない）。
  //   branding: {name, caption, qrPng?, cta?}（無ければ描かない）
  //            qrPng があれば（Sidekick QR の Secondary QR、2026-09-27 追加）、帯の左下に等倍・補間なしで置き、その右に name / caption / cta を並べる。
  //            Secondary QR は主 QR より小さくなければならない（SECONDARY_QR_TOO_LARGE）。qrPng が無いときの描画は追加前と同一。
  // → Promise<Blob>（image/png）
  async function compose(input) {
    if (!input || !(input.qrPng instanceof Blob) || input.qrPng.size === 0) {
      throw new CardEngineError("QR_MISSING", "no QR image");
    }
    if (typeof input.image !== "function") throw new CardEngineError("IMAGE_MISSING", "no image");

    const qr = await withObjectUrl(input.qrPng, loadImage);
    const qrWidth = qr.naturalWidth;
    const qrHeight = qr.naturalHeight;
    const pad = CARD.padding;
    const cardWidth = cardWidthFor(qrWidth);

    const brandQrPng = input.branding && input.branding.qrPng;
    const brandQr = brandQrPng instanceof Blob && brandQrPng.size > 0 ? await withObjectUrl(brandQrPng, loadImage) : null;
    if (brandQr && (brandQr.naturalWidth >= qrWidth || brandQr.naturalHeight >= qrHeight)) {
      throw new CardEngineError("SECONDARY_QR_TOO_LARGE", "the secondary QR must be smaller than the main QR");
    }
    const picture = await input.image(cardWidth);

    // 見出し・行が占める高さ（下の ③ と同じ送り幅）。Secondary QR はこの下に置くので、足りなければ帯を伸ばす。
    let textHeight = 76;
    for (const [label] of input.lines || []) textHeight += (label ? 36 : 0) + 60;
    const bandInner = brandQr ? Math.max(qrHeight, textHeight + 16 + brandQr.naturalHeight) : qrHeight;
    const bandHeight = bandInner + 2 * pad;
    const canvas = document.createElement("canvas");
    canvas.width = cardWidth;
    canvas.height = picture.areaHeight + bandHeight;
    const context = canvas.getContext("2d");
    const style = input.style || {};
    context.fillStyle = style.background || CARD.background;
    context.fillRect(0, 0, canvas.width, canvas.height);

    // ① 上段の画像（Adapter が決めた位置と大きさのまま）
    if (picture.areaFill) {
      context.fillStyle = picture.areaFill;
      context.fillRect(0, 0, cardWidth, picture.areaHeight);
    }
    context.drawImage(picture.source, picture.x, picture.y, picture.width, picture.height);
    if (picture.frame) {
      // 写真の周りの細線（整数座標の塗りつぶし 4 本。stroke の半 px のにじみを作らない）
      const f = picture.frame;
      context.fillStyle = f.color;
      context.fillRect(f.x, f.y, f.width, f.lineWidth);
      context.fillRect(f.x, f.y + f.height - f.lineWidth, f.width, f.lineWidth);
      context.fillRect(f.x, f.y, f.lineWidth, f.height);
      context.fillRect(f.x + f.width - f.lineWidth, f.y, f.lineWidth, f.height);
    }
    const rule = style.rule === undefined ? CARD.rule : style.rule;
    if (rule) {
      context.fillStyle = rule;
      context.fillRect(0, picture.areaHeight, cardWidth, 2);
    }

    // ② QR: 等倍・整数座標・補間なし。周りは白（quiet zone は PNG 自体が持っている）。
    const qrX = cardWidth - pad - qrWidth;
    const qrY = picture.areaHeight + pad;
    context.imageSmoothingEnabled = false;
    context.drawImage(qr, qrX, qrY);
    context.imageSmoothingEnabled = true;

    // ③ 見出し・行 と ④ branding（QR の外、左側）
    const textX = pad;
    const textWidth = qrX - 2 * pad;
    let y = qrY;
    drawText(context, input.title, textX, y, "700 44px system-ui, sans-serif", CARD.ink, textWidth);
    y += 76;
    for (const [label, value] of input.lines || []) {
      if (label) {
        drawText(context, label, textX, y, "600 26px system-ui, sans-serif", CARD.subInk, textWidth);
        y += 36;
      }
      drawText(context, value, textX, y, "400 36px system-ui, sans-serif", CARD.ink, textWidth);
      y += 60;
    }
    if (input.branding && brandQr) {
      // Secondary QR: 左下、等倍・整数座標・補間なし（quiet zone は PNG 自体が持っている）。文字はその右（QR に重ねない）。
      const brandQrX = pad;
      const brandQrY = picture.areaHeight + bandHeight - pad - brandQr.naturalHeight;
      context.imageSmoothingEnabled = false;
      context.drawImage(brandQr, brandQrX, brandQrY);
      context.imageSmoothingEnabled = true;
      const brandX = brandQrX + brandQr.naturalWidth + 24;
      const brandWidth = qrX - pad - brandX;
      let brandY = brandQrY + Math.max(0, Math.round((brandQr.naturalHeight - 134) / 2));
      drawText(context, input.branding.name, brandX, brandY, "700 52px system-ui, sans-serif", CARD.ink, brandWidth);
      brandY += 64;
      if (input.branding.caption) {
        drawText(context, input.branding.caption, brandX, brandY, "400 26px system-ui, sans-serif", CARD.subInk, brandWidth);
        brandY += 40;
      }
      if (input.branding.cta) {
        drawText(context, input.branding.cta, brandX, brandY, "600 26px system-ui, sans-serif", CARD.ink, brandWidth);
      }
    } else if (input.branding) {
      const brandY = picture.areaHeight + bandHeight - pad - 92;
      drawText(context, input.branding.name, textX, brandY, "700 52px system-ui, sans-serif", CARD.ink, textWidth);
      if (input.branding.caption) {
        drawText(context, input.branding.caption, textX, brandY + 64, "400 26px system-ui, sans-serif",
                 CARD.subInk, textWidth);
      }
    }

    return new Promise((resolve, reject) => {
      canvas.toBlob((blob) => (blob ? resolve(blob)
        : reject(new CardEngineError("ENCODE_FAILED", "the card could not be encoded"))), "image/png");
    });
  }

  root.SidekickCardEngine = Object.freeze({ compose, cardWidthFor, loadImage, withObjectUrl, CardEngineError, CARD });
})(typeof window === "undefined" ? globalThis : window);
