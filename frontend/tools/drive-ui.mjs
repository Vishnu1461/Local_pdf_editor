// Generic browser acceptance driver.
//
// Usage: node tools/drive-ui.mjs <file.pdf> [--base-url http://localhost:5173]
//
// Requires the backend and Vite dev server to be running. The script uploads
// the PDF, waits for detected fields, saves a copy, reopens it, and checks that
// the fields survived the round trip.
//
// Optional:
//   DRIVE_FIELD_TITLE  label/title of a field to edit before saving
//   DRIVE_VALUE        value to type into that field (default "TEST")
//   DRIVE_SHOTS        directory for before/after screenshots

import { chromium } from "playwright";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const args = process.argv.slice(2);
let baseUrl = "http://localhost:5173";
const positional = [];
for (let index = 0; index < args.length; index += 1) {
  if (args[index] === "--base-url") {
    baseUrl = args[index + 1] || baseUrl;
    index += 1;
    continue;
  }
  if (!args[index].startsWith("--")) positional.push(args[index]);
}
const pdfArg = positional[0];
if (!pdfArg) {
  console.error("usage: node tools/drive-ui.mjs <file.pdf> [--base-url http://localhost:5173]");
  process.exit(1);
}

const pdf = path.resolve(pdfArg);
if (!fs.existsSync(pdf)) {
  console.error(`PDF not found: ${pdf}`);
  process.exit(1);
}
const shots = process.env.DRIVE_SHOTS ? path.resolve(process.env.DRIVE_SHOTS) : "";
if (shots) fs.mkdirSync(shots, { recursive: true });

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1500, height: 1000 } });
const errors = [];
page.on("pageerror", (error) => errors.push(`pageerror: ${error.message}`));
page.on("console", (message) => {
  if (message.type() === "error") errors.push(`console: ${message.text()}`);
});

await page.goto(baseUrl);
await page.waitForSelector(".empty-card");
await page.locator('input[type="file"]').first().setInputFiles(pdf);
await page.waitForSelector(".field-box", { timeout: 180000 });
await page.waitForTimeout(1500);

const detected = await page.locator(".field-box").count();
if (detected === 0) throw new Error("no fields were detected; draw a field with the toolbar and retry");
await page.getByRole("button", { name: "Fit page" }).click();
await page.waitForTimeout(500);
if (shots) await page.screenshot({ path: path.join(shots, "01-loaded.png") });

const title = process.env.DRIVE_FIELD_TITLE;
if (title) {
  const field = page.locator(`.field-box[title="${title}"]`).first();
  await field.scrollIntoViewIfNeeded();
  await field.dblclick();
  await page.waitForSelector("input.inline-editor", { timeout: 10000 });
  await page.keyboard.type(process.env.DRIVE_VALUE || "TEST");
  await page.keyboard.press("Enter");
  await page.waitForTimeout(200);
  if (shots) await page.screenshot({ path: path.join(shots, "02-edited.png") });
}

const [download] = await Promise.all([
  page.waitForEvent("download", { timeout: 180000 }),
  page.getByRole("button", { name: "Save PDF" }).click(),
]);
const saved = path.join(os.tmpdir(), `pdf-form-editor-drive-${Date.now()}.pdf`);
await download.saveAs(saved);
await page.waitForSelector(".report", { timeout: 30000 });
const report = (await page.locator(".report").innerText()).replace(/\s+/g, " ").trim();

await page.getByRole("button", { name: "Open saved copy" }).click();
await page.waitForSelector(".field-box", { timeout: 180000 });
await page.waitForTimeout(1000);
const reopened = await page.locator(".field-box").count();
if (shots) await page.screenshot({ path: path.join(shots, "03-reopened.png") });

console.log(
  JSON.stringify(
    { detected, reopened, saved, report: report.slice(0, 240), errors },
    null,
    2,
  ),
);

await browser.close();
fs.rmSync(saved, { force: true });
if (reopened === 0) throw new Error("saved copy reopened with no fields");
if (errors.length) throw new Error(errors.join("\n"));
