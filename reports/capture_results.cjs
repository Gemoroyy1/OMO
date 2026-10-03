// Снимки фактических локальных страниц результатов.
const { chromium } = require('C:/Users/Admin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const { pathToFileURL } = require('url');
const path = require('path');
const fs = require('fs');
(async () => {
  const browser = await chromium.launch({executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe', headless:true});
  for (let i=1;i<=3;i++) {
    const dir=path.resolve(`Лаба${i}/reports/screenshots`);
    fs.mkdirSync(dir,{recursive:true});
    const page=await browser.newPage({viewport:{width:1100,height:850},deviceScaleFactor:1.5});
    const file=path.resolve(i===1?'Лаба1/reports/Все_результаты.html':`Лаба${i}/reports/results.html`);
    await page.goto(pathToFileURL(file).href);
    await page.screenshot({path:path.join(dir,'results_page.png')});
    await page.close();
  }
  await browser.close();
})();
