// Capture README screenshots and the demo GIF from the demo server.
//
//   node scripts/capture_media.mjs <python> [en|pt-br|es ...]
//
// Needs Google Chrome and ffmpeg. Writes into docs/media/. The demo server
// (scripts/demo_server.py) runs the real interface with a fictional fleet.
import { spawn } from "node:child_process";
import { mkdirSync, mkdtempSync, readdirSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";

const root = resolve(new URL("..", import.meta.url).pathname);
const media = join(root, "docs", "media");
const [python, ...requested] = process.argv.slice(2);
if (!python) {
  console.error("usage: node scripts/capture_media.mjs <python> [en|pt-br|es ...]");
  process.exit(2);
}
const languages = requested.length ? requested : ["en", "pt-br", "es"];
const sleep = (ms) => new Promise((done) => setTimeout(done, ms));
const WIDTH = 1360;
const HEIGHT = 850;

function run(command, args, options = {}) {
  return new Promise((done, fail) => {
    const child = spawn(command, args, { stdio: "inherit", ...options });
    child.on("exit", (code) => (code === 0 ? done() : fail(new Error(`${command} exited with ${code}`))));
  });
}

async function startDemo(language, port) {
  const child = spawn(python, [join(root, "scripts", "demo_server.py"), "--port", String(port), "--language", language]);
  let output = "";
  child.stdout.on("data", (chunk) => { output += chunk; });
  child.stderr.on("data", (chunk) => { output += chunk; });
  for (let i = 0; i < 100 && !/available at/.test(output); i++) await sleep(100);
  const targets = /Targets: (.+)/.exec(output)?.[1]?.trim();
  if (!targets) throw new Error(`demo server did not start:\n${output}`);
  return { child, targets, url: `http://127.0.0.1:${port}/` };
}

async function openBrowser(profile, port) {
  const chrome = spawn("google-chrome", ["--headless=new", "--disable-gpu", "--no-first-run", "--hide-scrollbars",
    `--user-data-dir=${profile}`, `--remote-debugging-port=${port}`, `--window-size=${WIDTH},${HEIGHT}`, "about:blank"], { stdio: "ignore" });
  let targets;
  for (let i = 0; i < 100 && !targets; i++) {
    try { targets = await (await fetch(`http://127.0.0.1:${port}/json`)).json(); } catch { await sleep(100); }
  }
  const ws = new WebSocket(targets.find((t) => t.type === "page").webSocketDebuggerUrl);
  await new Promise((done) => { ws.onopen = done; });
  let id = 0;
  const pending = new Map();
  ws.onmessage = (message) => {
    const data = JSON.parse(message.data);
    if (data.id && pending.has(data.id)) { pending.get(data.id)(data); pending.delete(data.id); }
  };
  const send = (method, params = {}) => new Promise((done) => {
    const callId = ++id;
    pending.set(callId, done);
    ws.send(JSON.stringify({ id: callId, method, params }));
  });
  const evaluate = async (expression) =>
    (await send("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true })).result?.result?.value;
  await send("Emulation.setDeviceMetricsOverride", { width: WIDTH, height: HEIGHT, deviceScaleFactor: 1.5, mobile: false });
  await send("Page.enable");
  return { chrome, ws, send, evaluate };
}

// A drawn pointer, so the recording shows where each click lands.
const CURSOR = `(() => {
  if (document.getElementById("demo-cursor")) return;
  const cursor = document.createElement("div");
  cursor.id = "demo-cursor";
  cursor.innerHTML = '<svg width="22" height="22" viewBox="0 0 24 24"><path d="M4 2l15 9-7 1.5L8.5 20z" fill="#fff" stroke="#000" stroke-width="1.4" stroke-linejoin="round"/></svg>';
  Object.assign(cursor.style, { position: "fixed", left: "760px", top: "520px", zIndex: 9999, pointerEvents: "none",
    transition: "left 0.45s ease, top 0.45s ease", filter: "drop-shadow(0 2px 3px rgba(0,0,0,.5))" });
  document.body.appendChild(cursor);
})()`;

async function capture(language, index) {
  const demo = await startDemo(language, 18800 + index);
  const profile = mkdtempSync(join(tmpdir(), "invenux-chrome-"));
  const browser = await openBrowser(profile, 9400 + index);
  const { send, evaluate } = browser;
  const suffix = language === "en" ? "en" : language;
  const frames = mkdtempSync(join(tmpdir(), "invenux-frames-"));
  let recording = false;
  let frame = 0;

  // Overlapping captureScreenshot calls return mixed frames; queue them.
  let queue = Promise.resolve();
  const screenshot = (params) => (queue = queue.then(() => send("Page.captureScreenshot", params)));
  const shot = async (name) => {
    const result = await screenshot({ format: "png" });
    writeFileSync(join(media, `${name}-${suffix}.png`), Buffer.from(result.result.data, "base64"));
  };
  let startedAt = 0;
  let stoppedAt = 0;
  const record = async () => {
    startedAt = Date.now();
    while (recording) {
      const result = await screenshot({ format: "jpeg", quality: 85 });
      writeFileSync(join(frames, `f${String(frame++).padStart(4, "0")}.jpg`), Buffer.from(result.result.data, "base64"));
      await sleep(70);
    }
    stoppedAt = Date.now();
  };
  // Clicks and typing go through the DOM (synthetic mouse events were flaky);
  // the drawn cursor still travels to each target first.
  const click = async (selector) => {
    let point;
    for (let i = 0; i < 50 && !Array.isArray(point); i++) {
      point = await evaluate(`(() => { const e = document.querySelector(${JSON.stringify(selector)}); if (!e) return null; const r = e.getBoundingClientRect(); return [r.x + r.width / 2, r.y + r.height / 2]; })()`);
      if (!Array.isArray(point)) await sleep(100);
    }
    if (!Array.isArray(point)) throw new Error(`not found: ${selector}`);
    await evaluate(`(() => { const c = document.getElementById("demo-cursor"); c.style.left = "${point[0] - 4}px"; c.style.top = "${point[1] - 3}px"; })()`);
    await sleep(520);
    await evaluate(`document.querySelector(${JSON.stringify(selector)}).click()`);
    await sleep(350);
  };
  const type = async (selector, text, delay = 55) => {
    await click(selector);
    await evaluate(`document.querySelector(${JSON.stringify(selector)}).focus()`);
    for (const character of text) {
      await evaluate(`(() => { const e = document.querySelector(${JSON.stringify(selector)}); e.value += ${JSON.stringify(character)}; e.dispatchEvent(new Event("input", { bubbles: true })); })()`);
      await sleep(delay);
    }
  };
  const commit = (selector) => evaluate(`document.querySelector(${JSON.stringify(selector)}).dispatchEvent(new Event("change", { bubbles: true }))`);

  await send("Page.navigate", { url: demo.url });
  await sleep(1500);
  await evaluate(CURSOR);
  await shot("onboarding");

  recording = true;
  const recorder = record();
  await sleep(2600);
  await click("#targets-trigger");
  await sleep(400);
  await type("#input-filepath", demo.targets, 18);
  await commit("#input-filepath");
  await sleep(1200);
  await type("#input-ssh-user", "inventory");
  await type("#input-ssh-pass", "correct-horse");
  await click("#scan-btn");
  await sleep(1400);
  await sleep(4200);
  await click("#hosts-tbody tr:nth-child(8)");
  await sleep(1200);
  await evaluate(`document.getElementById("inspector-pane").scrollTo({ top: 520, behavior: "smooth" })`);
  await sleep(1300);
  await click("#main-nav .nav-btn:nth-child(2)");
  await sleep(1800);
  await click("#main-nav .nav-btn:nth-child(1)");
  await click("#export-trigger");
  await click("#popover-export .menu-item:nth-child(1)");
  await sleep(1600);
  recording = false;
  await recorder;

  await evaluate(`document.getElementById("demo-cursor").remove()`);
  await evaluate(`document.getElementById("inspector-pane").scrollTo({ top: 0 })`);
  await sleep(300);
  await shot("hero");
  await evaluate(`switchView("dashboard", document.querySelectorAll("#main-nav .nav-btn")[1])`);
  await sleep(500);
  await shot("fleet");
  await evaluate(`switchView("scan", document.querySelectorAll("#main-nav .nav-btn")[0]); openHelp()`);
  await sleep(3700);
  await shot("help");
  await evaluate(`closeHelp()`);
  await send("Emulation.setDeviceMetricsOverride", { width: 760, height: 900, deviceScaleFactor: 1.5, mobile: false });
  await sleep(500);
  await shot("narrow");

  browser.ws.close();
  const closed = new Promise((done) => browser.chrome.on("exit", done));
  browser.chrome.kill();
  demo.child.kill();
  await closed;
  rmSync(profile, { recursive: true, force: true, maxRetries: 5, retryDelay: 200 });

  // Two-pass palette keeps the dark interface free of banding at a small size.
  const gif = join(media, `demo-${suffix}.gif`);
  // Frames arrive at whatever rate screenshots allow; play them back at that measured rate.
  const captureRate = (frame / ((stoppedAt - startedAt) / 1000)).toFixed(2);
  const filters = "fps=12,scale=960:-1:flags=lanczos";
  await run("ffmpeg", ["-y", "-loglevel", "error", "-framerate", captureRate, "-i", join(frames, "f%04d.jpg"),
    "-vf", `${filters},split[a][b];[a]palettegen=max_colors=128:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle`,
    gif]);
  console.log(`${language}: ${readdirSync(frames).length} frames at ${captureRate} fps -> ${gif}`);
  rmSync(frames, { recursive: true, force: true });

  // The Excel export from the recording, first page rendered by LibreOffice.
  const reports = join(dirname(demo.targets), "Documents", "Invenux");
  const workbook = readdirSync(reports).find((name) => name.endsWith(".xlsx"));
  const office = mkdtempSync(join(tmpdir(), "invenux-office-"));
  await run("soffice", [`-env:UserInstallation=file://${office}/profile`, "--headless", "--convert-to", "pdf", "--outdir", office, join(reports, workbook)], { stdio: "ignore" });
  await run("pdftoppm", ["-r", "110", "-png", "-f", "1", "-l", "1", "-singlefile", join(office, workbook.replace(".xlsx", ".pdf")), join(office, "page")]);
  await run("ffmpeg", ["-y", "-loglevel", "error", "-i", join(office, "page.png"), "-vf", "crop=iw-90:ih*0.62:45:60", join(media, `excel-${suffix}.png`)]);
  rmSync(office, { recursive: true, force: true });
}

mkdirSync(media, { recursive: true });
for (const [index, language] of languages.entries()) {
  await capture(language, index);
}
