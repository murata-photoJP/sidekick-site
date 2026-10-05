// server の受信口（api/_qr_map/viewer_decoder.generated.js）が share.html から 1 文字も変えずに
// 切り出したものであることを固定する（share.html が更新されたのに再生成を忘れると FAIL）。
//   node --test tests/qr_map/unit/
import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { buildModule, SOURCE_PATH, OUTPUT_PATH } from "../../../tools/qr_map/extract_viewer_decoder.mjs";

test("viewer_decoder.generated.js は share.html の受信口の写しと一致する", () => {
  const html = readFileSync(SOURCE_PATH, "utf8");
  // checkout の改行変換（Windows の CRLF）には左右されない。内容は 1 文字単位で一致させる
  assert.equal(readFileSync(OUTPUT_PATH, "utf8").replace(/\r\n/g, "\n"), buildModule(html));
});

test("写しは受信口と表示名 helper だけを含み、DOM 描画・通信の部分を含まない", () => {
  const generated = readFileSync(OUTPUT_PATH, "utf8");
  assert.match(generated, /async function decodeFragment\(fragment\)/);
  assert.match(generated, /function fromWireDictV2\(wire\)/);
  assert.match(generated, /function planTitle\(plan\)/);
  for (const forbidden of ["sendBeacon", "fetch(", "localStorage", "XMLHttpRequest", "new Image("]) {
    assert.ok(!generated.includes(forbidden), "含まれてはいけない: " + forbidden);
  }
});
