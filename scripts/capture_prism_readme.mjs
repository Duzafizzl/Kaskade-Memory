#!/usr/bin/env node
/**
 * capture_prism_readme.mjs – Render docs/assets/prism/*.mmd in mermaid-prism 2D.
 * Stills wait until the flow is on the last step. Spark/Rise also writes a short GIF.
 * Created: 2026-11-03
 * Last updated: 2026-11-03
 *
 * Needs a local mermaid-prism checkout (Playwright + Vite). Set MERMAID_PRISM.
 * Does not push. Does not start from CI.
 */
import { spawn } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, rmSync, statSync, writeFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = resolve(join(fileURLToPath(new URL(".", import.meta.url)), ".."));
const PRISM = process.env.MERMAID_PRISM
  ? resolve(process.env.MERMAID_PRISM)
  : [resolve(ROOT, "..", "mermaid-prism")].find((p) =>
      existsSync(join(p, "playground", "kaskade-still.html")),
    );

const PORT = Number(process.env.PRISM_PG_PORT ?? 5180);
const FFMPEG = process.env.FFMPEG ?? "/opt/homebrew/bin/ffmpeg";
const OUT = join(ROOT, "docs", "assets");
const TMP = join(ROOT, "tmp", "prism-capture");
const SCENES = [
  { id: "cascade", mmd: "cascade.mmd", webp: "prism-cascade-2d.webp" },
  { id: "lifetimes", mmd: "lifetimes.mmd", webp: "prism-lifetimes-2d.webp" },
  { id: "spark-rise", mmd: "spark-rise.mmd", webp: "prism-spark-rise-2d.webp", gif: "prism-spark-rise-2d.gif" },
];

function say(s) {
  process.stdout.write(s);
}

function log(level, event, fields = {}) {
  process.stderr.write(
    JSON.stringify({ ts: new Date().toISOString(), level, module: "capture_prism_readme", event, ...fields }) + "\n",
  );
}

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

function run(bin, args) {
  return new Promise((resolve, reject) => {
    const p = spawn(bin, args, { stdio: ["ignore", "ignore", "pipe"] });
    let err = "";
    p.stderr.on("data", (d) => {
      err += d;
    });
    p.on("close", (code) => (code === 0 ? resolve() : reject(new Error(`${bin} ${code}: ${err.slice(-400)}`))));
  });
}

async function waitPort(port, ms = 20000) {
  const t0 = Date.now();
  while (Date.now() - t0 < ms) {
    try {
      const res = await fetch(`http://127.0.0.1:${port}/kaskade-still.html`, { method: "HEAD" });
      if (res.ok || res.status === 405 || res.status === 200) return;
    } catch {
      /* still booting */
    }
    await sleep(250);
  }
  throw new Error(`playground did not listen on ${port}`);
}

async function mountScene(page, code) {
  await page.goto(`http://127.0.0.1:${PORT}/kaskade-still.html`, { waitUntil: "domcontentloaded" });
  await page.waitForFunction(() => window.__stillReady === true, { timeout: 20000 });
  const ok = await page.evaluate(async (src) => window.renderKaskadeStill(src), code);
  if (!ok) throw new Error("Prism 2D did not mount");
  await page.waitForFunction(() => document.querySelector("#stage .prism"), { timeout: 20000 });
  await sleep(700);
}

async function clipOf(page) {
  const box = await page.locator("#stage .prism").boundingBox();
  if (!box || box.width < 40 || box.height < 40) throw new Error("empty prism box");
  const pad = 40;
  const vw = 1440;
  const vh = 820;
  return {
    x: Math.max(0, box.x - pad),
    y: Math.max(0, box.y - pad),
    width: Math.min(vw - Math.max(0, box.x - pad), box.width + pad * 2),
    height: Math.min(vh - Math.max(0, box.y - pad), box.height + pad * 2),
  };
}

if (!PRISM) {
  say("ERROR: set MERMAID_PRISM to a mermaid-prism checkout with playground/kaskade-still.html\n");
  process.exit(2);
}

say("╔════════════════════════════════════════════════╗\n");
say("║   Kaskade · Prism 2D stills + Spark/Rise GIF   ║\n");
say("╚════════════════════════════════════════════════╝\n\n");
say("This may take a while, please wait...\n");
say(`STEP 1: Playground  ${PRISM}\n`);

mkdirSync(TMP, { recursive: true });

const { chromium } = await import(join(PRISM, "node_modules", "playwright", "index.mjs"));

let vite = null;
try {
  await waitPort(PORT, 800);
  say("  already up\n");
} catch {
  vite = spawn("npm", ["run", "dev", "--", "--host", "127.0.0.1", "--port", String(PORT)], {
    cwd: PRISM,
    stdio: ["ignore", "pipe", "pipe"],
  });
  await waitPort(PORT, 30000);
  say("  started\n");
}

say("STEP 2: Capture\n");
const browser = await chromium.launch({ channel: "chrome", headless: true });
const page = await browser.newPage({
  viewport: { width: 1440, height: 820 },
  deviceScaleFactor: 2,
});

let n = 0;
for (const scene of SCENES) {
  n += 1;
  const pct = ((n / SCENES.length) * 100).toFixed(1);
  say(`  [${n}/${SCENES.length}] (${pct}%) ${scene.id} still …\n`);
  const code = readFileSync(join(OUT, "prism", scene.mmd), "utf8").replace(/^%%.*\n/gm, "").trim();
  await mountScene(page, code);
  await page.addStyleTag({ content: `.prism-player, .prism-drill { display: none !important; }` });
  const finished = await page.evaluate(() => window.finishFlow());
  await sleep(800);
  const clip = await clipOf(page);
  const png = join(TMP, `${scene.id}.png`);
  await page.screenshot({ path: png, type: "png", clip });
  await run("cwebp", ["-quiet", "-q", "84", png, "-o", join(OUT, scene.webp)]);
  say(`  ✅ [${n}/${SCENES.length}] (${pct}%) ${scene.webp}  step ${finished.step + 1}/${finished.stepCount}\n`);
  log("info", "still_ok", { scene: scene.id, webp: scene.webp, ...finished });

  if (!scene.gif) continue;
  say(`  [${n}/${SCENES.length}] (${pct}%) ${scene.id} gif …\n`);
  await mountScene(page, code);
  await page.addStyleTag({ content: `.prism-player, .prism-drill { display: none !important; }` });
  const started = await page.evaluate(() => window.playFlow(1.75));
  if (!started) throw new Error(`${scene.id}: no flow player`);
  const framesDir = join(TMP, `${scene.id}-frames`);
  rmSync(framesDir, { recursive: true, force: true });
  mkdirSync(framesDir, { recursive: true });
  let i = 0;
  const t0 = Date.now();
  while (Date.now() - t0 < 12000) {
    const clipGif = await clipOf(page);
    await page.screenshot({ path: join(framesDir, `f${String(i).padStart(4, "0")}.png`), type: "png", clip: clipGif });
    i += 1;
    const playing = await page.evaluate(() => window.flowPlaying());
    if (!playing && i > 8) break;
    await sleep(70);
  }
  const list = join(framesDir, "frames.txt");
  const names = Array.from({ length: i }, (_, k) => `f${String(k).padStart(4, "0")}.png`);
  writeFileSync(
    list,
    names.flatMap((name, k) => {
      const file = join(framesDir, name);
      const dur = k === names.length - 1 ? 0.7 : 0.07;
      return [`file '${file.replace(/'/g, "'\\''")}'`, `duration ${dur}`];
    }).concat([`file '${join(framesDir, names.at(-1)).replace(/'/g, "'\\''")}'`]).join("\n") + "\n",
  );
  const gif = join(OUT, scene.gif);
  const vf =
    "fps=12,scale=960:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=128:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=4";
  await run(FFMPEG, ["-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", list, "-vf", vf, "-loop", "0", gif]);
  const bytes = statSync(gif).size;
  if (bytes > 2 * 1024 * 1024) {
    say(`  ↻ gif ${(bytes / 1024 / 1024).toFixed(2)} MB, smaller pass\n`);
    const vf2 =
      "fps=10,scale=800:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=96:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=4";
    await run(FFMPEG, ["-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", list, "-vf", vf2, "-loop", "0", gif]);
  }
  say(`  ✅ [${n}/${SCENES.length}] (${pct}%) ${scene.gif}  ${(statSync(gif).size / 1024).toFixed(0)} KB\n`);
  log("info", "gif_ok", { scene: scene.id, gif: scene.gif, bytes: statSync(gif).size, frames: i });
}

await browser.close();
if (vite) vite.kill("SIGTERM");
say("\nSTEP 3: Done\n");
