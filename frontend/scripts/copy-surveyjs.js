/**
 * Copy unhashed SurveyJS vanilla min files into Django static/surveyjs/.
 *
 * Admin templates use {% static 'surveyjs/...' %}; hashed webpack chunks
 * would break those paths. Re-run after upgrading survey-* / Chart.js deps:
 *
 *   npm run copy-surveyjs
 *
 * survey-analytics 3.x defaults to Chart.js (not Plotly).
 */
const fs = require("fs");
const path = require("path");

const frontendRoot = path.join(__dirname, "..");
const destDir = path.join(frontendRoot, "..", "static", "surveyjs");

const files = [
  ["node_modules/survey-core/survey.core.min.js", "survey.core.min.js"],
  ["node_modules/survey-core/survey-core.min.css", "survey-core.min.css"],
  ["node_modules/survey-js-ui/survey-js-ui.min.js", "survey-js-ui.min.js"],
  ["node_modules/survey-creator-core/survey-creator-core.min.js", "survey-creator-core.min.js"],
  ["node_modules/survey-creator-core/survey-creator-core.min.css", "survey-creator-core.min.css"],
  ["node_modules/survey-creator-js/survey-creator-js.min.js", "survey-creator-js.min.js"],
  ["node_modules/survey-analytics/survey.analytics.min.js", "survey.analytics.min.js"],
  ["node_modules/survey-analytics/survey.analytics.min.css", "survey.analytics.min.css"],
  ["node_modules/chart.js/dist/chart.umd.min.js", "chart.umd.min.js"],
  ["node_modules/survey-core/i18n/simplified-chinese.min.js", "survey.i18n.zh-cn.min.js"],
  ["node_modules/survey-creator-core/i18n/simplified-chinese.min.js", "survey-creator.i18n.zh-cn.min.js"],
];

fs.mkdirSync(destDir, { recursive: true });

let failed = false;
for (const [srcRel, destName] of files) {
  const src = path.join(frontendRoot, srcRel);
  if (!fs.existsSync(src)) {
    console.error(`copy-surveyjs: missing ${srcRel}`);
    failed = true;
    continue;
  }
  fs.copyFileSync(src, path.join(destDir, destName));
  console.log(`copied ${destName}`);
}

if (failed) {
  process.exit(1);
}
