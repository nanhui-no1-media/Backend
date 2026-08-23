/**
 * Build-seam check for 看板娘 Live2D static assets.
 * Hooked at the end of `npm run build`. No test runner.
 */
const fs = require("fs");
const path = require("path");

const distRoot = path.join(__dirname, "..", "dist", "live2d");
const required = [
  "runtime/live2d.min.js",
  "catalog.json",
  "widget/waifu.css",
  "widget/waifu-tips.js",
];

function fail(message) {
  console.error(`assert-live2d-dist: ${message}`);
  process.exit(1);
}

if (!fs.existsSync(distRoot)) {
  fail(`missing directory ${distRoot}`);
}

for (const rel of required) {
  const abs = path.join(distRoot, rel);
  if (!fs.existsSync(abs)) {
    fail(`missing ${path.join("dist", "live2d", rel)}`);
  }
}

const catalogPath = path.join(distRoot, "catalog.json");
let catalog;
try {
  catalog = JSON.parse(fs.readFileSync(catalogPath, "utf8"));
} catch (err) {
  fail(`catalog.json is not valid JSON: ${err.message}`);
}

if (catalog.version !== 1 || !Array.isArray(catalog.models) || catalog.models.length < 1) {
  fail("catalog.json must have version 1 and a non-empty models array");
}

const first = catalog.models[0];
if (!first.id || !first.entry) {
  fail("catalog.json first model must have id and entry");
}

const entryPath = path.join(distRoot, first.entry);
if (!fs.existsSync(entryPath)) {
  fail(`default model entry missing: ${first.entry}`);
}

const licenseHits = [];
function walk(dir) {
  for (const name of fs.readdirSync(dir, { withFileTypes: true })) {
    const abs = path.join(dir, name.name);
    if (name.isDirectory()) walk(abs);
    else if (/^license/i.test(name.name)) licenseHits.push(abs);
  }
}
walk(distRoot);
if (licenseHits.length < 1) {
  fail("no LICENSE text copied into dist/live2d");
}

console.log(
  `assert-live2d-dist: ok (${catalog.models.length} models, default=${first.id}, licenses=${licenseHits.length})`,
);
