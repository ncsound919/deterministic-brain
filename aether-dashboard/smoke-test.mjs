import { chromium } from 'playwright';

const BASE = 'http://localhost:5173';
const ROUTES = [
  { path: '/', name: 'Dashboard' },
  { path: '/#/systems', name: 'Systems Health' },
  { path: '/#/intel', name: 'Intel Hub' },
  { path: '/#/scheduler', name: 'Scheduler' },
  { path: '/#/skills', name: 'Skill Marketplace' },
  { path: '/#/browser', name: 'Browser Automation' },
  { path: '/#/github', name: 'GitHub Manager' },
  { path: '/#/content', name: 'Content Social' },
  { path: '/#/research', name: 'Research Lab' },
];

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext();
const page = await context.newPage();

const results = [];

for (const route of ROUTES) {
  const url = `${BASE}${route.path}`;
  const consoleErrors = [];
  const pageErrors = [];

  page.removeAllListeners('console');
  page.removeAllListeners('pageerror');
  page.on('console', msg => {
    if (msg.type() === 'error') {
      consoleErrors.push(msg.text());
    }
  });
  page.on('pageerror', err => {
    pageErrors.push(err.message);
  });

  try {
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 15000 });
    await page.waitForTimeout(2500);

    // For hash routes, we use url() to check current URL since no network request is made
    const currentUrl = page.url();
    const title = await page.title();
    // Check for root element to confirm React rendered
    const rootExists = await page.$('#root') !== null;
    // Look for any visible text content
    const bodyText = await page.evaluate(() => document.body.innerText?.slice(0, 200) || '');

    // Pages that show 'no-response' for status are actually fine for hash routing
    const isHashRoute = route.path.includes('#');
    const effectiveStatus = isHashRoute ? (rootExists ? 200 : 0) : 200;

    // Filter out known benign errors
    const realErrors = consoleErrors.filter(e =>
      !e.includes('favicon') &&
      !e.includes('manifest') &&
      !e.includes('net::ERR_NOTFOUND')
    );

    const ok = rootExists &&
               pageErrors.length === 0 &&
               realErrors.length === 0 &&
               bodyText.trim().length > 10;

    results.push({
      name: route.name,
      url,
      status: effectiveStatus,
      title,
      hasContent: bodyText.trim().length > 10,
      pageErrors: [...pageErrors],
      consoleErrors: realErrors,
      ok
    });
  } catch (e) {
    results.push({
      name: route.name,
      url,
      status: 'CRASH',
      error: e.message.slice(0, 200),
      ok: false
    });
  }
}

await browser.close();

console.log('\n=== PLAYWRIGHT SMOKE TEST RESULTS ===\n');
let allOk = true;
for (const r of results) {
  const mark = r.ok ? '✅' : '❌';
  console.log(`${mark} ${r.name}`);
  console.log(`   URL: ${r.url}`);
  console.log(`   Status: ${r.status} | Has Content: ${r.hasContent ? 'YES' : 'NO'}`);
  if (r.consoleErrors?.length) console.log(`   Console Errors (${r.consoleErrors.length}): ${r.consoleErrors.slice(0, 3).join('\n       ')}`);
  if (r.pageErrors?.length) console.log(`   Page Errors (${r.pageErrors.length}): ${r.pageErrors.slice(0, 3).join('\n       ')}`);
  if (r.error) console.log(`   Exception: ${r.error}`);
  if (!r.ok) allOk = false;
}

console.log(`\n${allOk ? '✅ ALL PAGES PASSED' : '❌ SOME PAGES FAILED'}`);
process.exit(allOk ? 0 : 1);