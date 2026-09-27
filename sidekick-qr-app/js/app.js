// Sidekick QR —— 画面（UI）と保存（Exporter）（HD-SIDEKICKQR-002、AI-15970）。
//
// 画像を選ぶ → URL を入力 → タイトル（必須）・説明（任意）→［カードを作成］→ Card preview →［PNGとして保存］。
// 由来: Generic Image Card prototype の `startPage`（docs/PROVENANCE.md）。状態の扱いは移植元と同じ:
//   * **表示している Card の bytes をそのまま保存する**（保存のために作り直さない）
//   * 入力を変えると表示中の Card を捨てる（古い Card を保存させない）
// **privacy 境界**: 画像・URL・Card を外へ送らない（この file は fetch / XHR / beacon / WebSocket を使わない。page の CSP も `connect-src 'none'`）。
"use strict";

(function (root) {
  const SAVE_FILENAME = "sidekick-qr-card.png";

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
    let bitmap = null;
    let current = null;                   // {blob, url} —— 表示中 = 保存される Card
    let sequence = 0;

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

    photoInput.addEventListener("change", async () => {
      inputsChanged();
      if (bitmap) { bitmap.close(); bitmap = null; }
      $("photo-info").textContent = "";
      const file = photoInput.files && photoInput.files[0];
      if (!file) return;
      try {
        bitmap = await root.SidekickQrImage.decodePhoto(file);
        $("photo-info").textContent = bitmap.width + " × " + bitmap.height + " px";
        setStatus("", false);
      } catch (error) {
        photoInput.value = "";
        setStatus(error.message, true);
      }
    });
    for (const input of [titleInput, descriptionInput]) input.addEventListener("input", inputsChanged);
    urlInput.addEventListener("input", () => { inputsChanged(); checkUrlField(); });

    makeButton.addEventListener("click", async () => {
      discardCard();
      const title = titleInput.value.trim();
      const description = descriptionInput.value.trim();
      const checked = checkUrlField();
      const problems = [];
      if (!bitmap) problems.push("画像を選んでください。");
      if (!checked) problems.push("リンク先URLを入力してください。");
      else if (!checked.ok) problems.push(...checked.errors);
      if (!title) problems.push("タイトルを入力してください。");
      if (problems.length) { setStatus(problems.join(" "), true); return; }
      const mine = sequence;
      makeButton.disabled = true;
      setStatus("カードを作っています…", false);
      try {
        const built = await root.SidekickQrCard.render({ bitmap, title, description, href: checked.href });
        if (mine !== sequence) return;                  // 作っている間に入力が変わった
        current = { blob: built.card, url: URL.createObjectURL(built.card) };
        image.src = current.url;
        $("encoded-url").textContent = checked.href;
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

  root.SidekickQrApp = Object.freeze({ SAVE_FILENAME });
  if (typeof document !== "undefined" && document.getElementById("make-card")) {
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
    else start();
  }
})(typeof window === "undefined" ? globalThis : window);
