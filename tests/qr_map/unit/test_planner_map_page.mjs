// プランナーQRマップ page の静的な構造（G-3.3 導入カード）。browser の確認は tests/qr_map/browser/。
import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";

const html = readFileSync(new URL("../../../planner-map.html", import.meta.url), "utf8");
const text = (s) => s.replace(/<[^>]+>/g, "");

test("G-3.3: 導入カードに main message・pin の説明・数字の pin の説明がある", () => {
  const h1 = html.match(/<h1[^>]*>([\s\S]*?)<\/h1>/);
  assert.ok(h1, "h1 がある");
  assert.equal((html.match(/<h1[\s>]/g) || []).length, 1);
  assert.match(text(h1[1]), /プランナーQRマップ/);
  assert.match(text(h1[1]), /みんなの撮影計画から、次に撮りたい場所を探そう。/);
  assert.match(text(html), /ピンを選ぶと、撮影日時・被写体・撮影計画を見ることができます。/);
  assert.match(text(html), /数字のピンは、この付近にある計画の数です。/);
});

test("G-3.3: First Action Cue は読み上げず（aria-hidden）、最初は hidden（JS が pin のあるときだけ出す）", () => {
  const cue = html.match(/<p id="pm-cue"[^>]*>/);
  assert.ok(cue);
  assert.match(cue[0], /aria-hidden="true"/);
  assert.match(cue[0], /\shidden[\s>]/);
});

test("G-3.3: 凡例の pin は装飾（aria-hidden）で、外部 resource を読まない", () => {
  assert.equal((html.match(/class="pm-legend[^"]*" aria-hidden="true"/g) || []).length, 2);
  assert.doesNotMatch(html, /<script[^>]+src="https?:/);
  assert.doesNotMatch(html, /<link[^>]+href="https?:/);
  assert.match(html, /name="robots" content="noindex, nofollow"/);
});
