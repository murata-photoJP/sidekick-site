// Sidekick QR —— 画面（UI）と保存（Exporter）（HD-SIDEKICKQR-002、AI-15970）。
//
// 画像を選ぶ → URL を入力 → タイトル（必須）・説明（任意）→［カードを作成］→ Card preview →［PNGとして保存］。
// mode（HD-SIDEKICKQR-026）: URL mode = 入力した URL が Primary QR（今までどおり）/ EXIF mode = 写真の許可した撮影情報の text が Primary QR。
//   EXIF は **EXIF mode を選んだときだけ** 読む（exif_reader.js、allow-list）。読んだ内容は画面に表示し、Primary QR には同じ内容を
//   EXIF Viewer の URL（https://www.sidekick-lab.com/exif#v=1&…、HD-SIDEKICKQR-028）として入れる。QR を読んだ人の画面には表示どおりの撮影情報が出る。
// 由来: Generic Image Card prototype の `startPage`（docs/PROVENANCE.md）。状態の扱いは移植元と同じ:
//   * **表示している Card の bytes をそのまま保存する**（保存のために作り直さない）
//   * 入力を変えると表示中の Card を捨てる（古い Card を保存させない）
// **privacy 境界**: 画像・URL・Card を外へ送らない（この file は fetch / XHR / beacon / WebSocket を使わない。page の CSP も `connect-src 'none'`）。
"use strict";

(function (root) {
  const SAVE_FILENAME = "sidekick-qr-card.png";
  const NO_EXIF_MESSAGE = "撮影情報がありません。URLモードを使ってください。";

  function start() {
    const $ = (id) => document.getElementById(id);
    const photoInput = $("photo");
    const titleInput = $("title");
    const descriptionInput = $("description");
    const urlInput = $("url");
    const makeButton = $("make-card");
    const saveButton = $("save-card");
    const result = $("result");
    const image = $("card-image");
    const status = $("status");
    const modeInputs = [$("mode-url"), $("mode-exif")];
    const exifPreview = $("exif-preview");
    let bitmap = null;
    let photoFile = null;
    let exifText = null;                  // EXIF mode で読んだ撮影情報の表示（null = まだ読んでいない、"" = 撮影情報なし）
    let exifUrl = "";                     // 同じ撮影情報の EXIF Viewer の URL（Primary QR に入る）
    let current = null;                   // {blob, url} —— 表示中 = 保存される Card
    let sequence = 0;
    let exifSequence = 0;
    const mode = () => ($("mode-exif").checked ? "exif" : "url");

    const setStatus = (text, isError) => {
      status.textContent = text || "";
      status.classList.toggle("error", Boolean(isError));
    };
    const showList = (id, items, isError) => {
      const list = $(id);
      list.replaceChildren(...items.map((item) => { const li = document.createElement("li"); li.textContent = item; return li; }));
      list.hidden = items.length === 0;
      list.classList.toggle("error", Boolean(isError));
    };
    const discardCard = () => {
      sequence += 1;
      if (current) URL.revokeObjectURL(current.url);
      current = null;
      image.removeAttribute("src");
      result.hidden = true;
      saveButton.disabled = true;
    };
    const inputsChanged = () => {
      const hadCard = Boolean(current);
      discardCard();
      if (hadCard) setStatus("入力が変わりました。もう一度［カードを作成］を押してください。", false);
    };

    const checkUrlField = () => {
      const value = urlInput.value.trim();
      if (!value) { showList("url-messages", [], false); return null; }
      const checked = root.SidekickQrUrlPolicy.checkUrl(value);
      showList("url-messages", checked.ok ? checked.warnings : checked.errors, !checked.ok);
      return checked;
    };

    // EXIF mode のときだけ、選んだ写真の撮影情報を読んで表示する（URL mode では読まない）
    const readExif = async () => {
      exifSequence += 1;
      const mine = exifSequence;
      exifText = null;
      exifUrl = "";
      exifPreview.textContent = "";
      showList("exif-messages", [], false);
      if (mode() !== "exif" || !photoFile) return;
      let text = "";
      let url = "";
      try {
        const model = await root.SidekickQrExif.readFile(photoFile);
        text = root.SidekickQrExif.serialize(model, "ja");
        url = text ? root.SidekickQrExif.viewerUrl(model) : "";
      } catch (_) {
        text = "";
        url = "";
      }
      if (mine !== exifSequence) return;                    // 読んでいる間に写真・mode が変わった
      exifText = text;
      exifUrl = url;
      exifPreview.textContent = text || NO_EXIF_MESSAGE;
      // 日本語等で QR が大きくなるとき: 作れるが、URL mode と同じ「細かくなる」警告を出す（HD-SIDEKICKQR-028、v25 以上）
      if (url) {
        let version = 0;
        try { version = root.SidekickQr.encode(url, { ecc: "M" }).version; } catch (_) { version = 99; }
        if (version >= root.SidekickQrUrlPolicy.DENSE_QR_VERSION) {
          showList("exif-messages", ["撮影情報が長いのでQRコードが細かくなります。小さく印刷すると読み取りにくくなります。"], false);
        }
      }
    };

    const applyMode = () => {
      const exif = mode() === "exif";
      $("url-section").hidden = exif;
      $("exif-section").hidden = !exif;
      $("mode-hint-url").hidden = exif;
      $("mode-hint-exif").hidden = !exif;
    };
    for (const input of modeInputs) {
      input.addEventListener("change", () => { inputsChanged(); applyMode(); readExif(); });
    }
    applyMode();

    photoInput.addEventListener("change", async () => {
      inputsChanged();
      if (bitmap) { bitmap.close(); bitmap = null; }
      photoFile = null;
      $("photo-info").textContent = "";
      const file = photoInput.files && photoInput.files[0];
      if (!file) { readExif(); return; }
      try {
        bitmap = await root.SidekickQrImage.decodePhoto(file);
        photoFile = file;
        $("photo-info").textContent = bitmap.width + " × " + bitmap.height + " px";
        setStatus("", false);
      } catch (error) {
        photoInput.value = "";
        setStatus(error.message, true);
      }
      await readExif();
    });
    for (const input of [titleInput, descriptionInput]) input.addEventListener("input", inputsChanged);
    urlInput.addEventListener("input", () => { inputsChanged(); checkUrlField(); });

    makeButton.addEventListener("click", async () => {
      discardCard();
      const title = titleInput.value.trim();
      const description = descriptionInput.value.trim();
      const cardMode = mode();
      const checked = cardMode === "url" ? checkUrlField() : null;
      const problems = [];
      if (!bitmap) problems.push("画像を選んでください。");
      if (cardMode === "url") {
        if (!checked) problems.push("リンク先URLを入力してください。");
        else if (!checked.ok) problems.push(...checked.errors);
      } else if (bitmap && exifText === null) {
        problems.push("撮影情報を読み込んでいます。少し待ってから、もう一度押してください。");
      } else if (bitmap && !exifText) {
        problems.push(NO_EXIF_MESSAGE);
      }
      if (!title) problems.push("タイトルを入力してください。");
      if (problems.length) { setStatus(problems.join(" "), true); return; }
      const payload = cardMode === "url" ? checked.href : exifUrl;
      const mine = sequence;
      makeButton.disabled = true;
      setStatus("カードを作っています…", false);
      try {
        const built = await root.SidekickQrCard.render({ mode: cardMode, bitmap, title, description, href: payload });
        if (mine !== sequence) return;                  // 作っている間に入力が変わった
        current = { blob: built.card, url: URL.createObjectURL(built.card) };
        image.src = current.url;
        $("encoded-label").textContent = cardMode === "url" ? "QRコードに入っているURL:" : "QRコードに入っているURL（撮影情報のページ）:";
        $("encoded-url").textContent = built.payload;
        result.hidden = false;
        saveButton.disabled = false;
        setStatus("カードができました。内容を確認して［PNGとして保存］を押してください。", false);
      } catch (error) {
        if (mine === sequence) setStatus("カードを作れませんでした。画像や入力を変えて、もう一度お試しください。", true);
      } finally {
        makeButton.disabled = false;
      }
    });

    // Exporter: **表示している Card の bytes をそのまま保存する**。
    saveButton.addEventListener("click", () => {
      if (!current) return;
      const link = document.createElement("a");
      link.href = current.url;
      link.download = SAVE_FILENAME;
      document.body.appendChild(link);
      link.click();
      link.remove();
    });
  }

  root.SidekickQrApp = Object.freeze({ SAVE_FILENAME, NO_EXIF_MESSAGE });
  if (typeof document !== "undefined" && document.getElementById("make-card")) {
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
    else start();
  }
})(typeof window === "undefined" ? globalThis : window);
