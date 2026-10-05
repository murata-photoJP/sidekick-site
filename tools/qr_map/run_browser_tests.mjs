// プランナーQRマップ（G-3）の browser test を Firestore Emulator 上で走らせる。
//
//   npm run test:qr-map:browser
//   （= firebase emulators:exec … "node tools/qr_map/run_browser_tests.mjs"）
//
// dev server（本物の api/qr-map.js）を空き port で起動 → seed（publish API 経由）→ Python Playwright の test
// （tests/qr_map/browser/）を実行。地理院タイルは test 内で 1×1 PNG に差し替える（GSI へ負荷をかけない）。
import { spawn } from "node:child_process";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { ROOT, startServer } from "./dev_server.mjs";
import { seedEmulator } from "./seed_emulator.mjs";

const work = mkdtempSync(join(tmpdir(), "planner-map-browser-"));
const manifestPath = join(work, "seed_manifest.json");
const { server, baseUrl } = await startServer({ port: 0 });
const manifest = await seedEmulator({ baseUrl, manifestPath });
console.log("seeded:", JSON.stringify(manifest.summary), "→", baseUrl);

const python = process.env.PLANNER_MAP_PYTHON || (process.platform === "win32" ? "py" : "python3");
const args = process.platform === "win32" && !process.env.PLANNER_MAP_PYTHON ? ["-3.10"] : [];
const child = spawn(python, [...args, "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests/qr_map/browser"], {
  cwd: ROOT,
  stdio: "inherit",
  env: { ...process.env, PLANNER_MAP_BASE_URL: baseUrl, PLANNER_MAP_SEED_MANIFEST: manifestPath, PLANNER_MAP_ARTIFACTS: work }
});
const code = await new Promise((resolve) => child.on("exit", resolve));
server.close();
console.log("browser artifacts:", work);
process.exit(code === null ? 1 : code);
