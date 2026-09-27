// Sidekick QR —— 起動の確認（L-1 guard、HD-SIDEKICKQR-014 B、AI-15982）。bootstrap 層だけで、Card / QR / 画像 / URL の処理には関わらない。
//
// index.html の #startup-guard（「Sidekick QR を起動できませんでした。… すべて展開 …」）は、何もしなければ少し遅れて表示される（CSS の animation-delay）。
// この script は最後に読まれ、必要な部品（script 6 本が作る global）がすべて揃っていれば guard を取り除く。
//   * 正常: guard は表示される前に消える（画面・操作・Card は今までと同じ）
//   * ZIP の中から直接開いた等で script が読めない: この file も読めないので、guard がそのまま表示される（「カードを作成」が無言になる状態にしない）
//   * 一部の script だけ読めない: guard をすぐに表示し、「カードを作成」を押せなくする
// 起動方法を URL の文字列で推測しない（実際に部品が揃ったかだけを見る）。通信しない。
"use strict";

(function (root) {
  const REQUIRED = ["SidekickCardEngine", "SidekickQr", "SidekickQrImage", "SidekickQrUrlPolicy", "SidekickQrCard", "SidekickQrApp"];
  const guard = document.getElementById("startup-guard");
  if (!guard) return;
  const missing = REQUIRED.filter((name) => !root[name]);
  if (missing.length === 0) {
    guard.remove();
    return;
  }
  guard.classList.add("shown");
  const button = document.getElementById("make-card");
  if (button) button.disabled = true;
})(typeof window === "undefined" ? globalThis : window);
