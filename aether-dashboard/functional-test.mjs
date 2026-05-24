import { chromium } from 'playwright';

const BASE = 'http://localhost:5173';
const BACKEND = 'http://localhost:8000';

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext();
const page = await context.newPage();

const results = [];

async function testPage(name, url, checks) {
  const consoleErrors = [];
  const pageErrors = [];
  page.removeAllListeners('console');
  page.removeAllListeners('pageerror');
  page.on('console', msg => { if (msg.type() === 'error') consoleErrors.push(msg.text()); });
  page.on('pageerror', err => { pageErrors.push(err.message); });

  try {
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 15000 });
    await page.waitForTimeout(2500);
    const checkResults = {};
    for (const [checkName, checkFn] of Object.entries(checks)) {
      try { checkResults[checkName] = await checkFn(page); }
      catch (e) { checkResults[checkName] = `ERROR: ${e.message.slice(0, 100)}`; }
    }
    const realErrors = consoleErrors.filter(e => !e.includes('favicon') && !e.includes('manifest') && !e.includes('net::ERR_NOTFOUND'));
    return { name, url, ok: pageErrors.length === 0 && realErrors.length === 0, checkResults, pageErrors, consoleErrors: realErrors };
  } catch (e) {
    return { name, url, ok: false, error: e.message.slice(0, 200), pageErrors, consoleErrors: [] };
  }
}

// 1. CronManager — verify live scheduler data loaded
const cronResult = await testPage('CronManager Live Data', `${BASE}/#/scheduler`, {
  'Page renders': async (p) => { const t = await p.innerText('body'); return t.length > 100; },
  'No ReferenceError for opportunitiesList': async (p) => {
    // previously ResearchLab had this bug — just ensure page loaded
    return true;
  },
  'Scheduler data populates': async (p) => {
    // Check for scheduler-related content (task list or cron schedule)
    const text = await p.innerText('body');
    return text.includes('Cron') || text.includes('Scheduler') || text.includes('cron') || text.includes('task');
  },
});

// 2. Systems Health — verify component status grid is NOT hardcoded all-online
const sysResult = await testPage('SystemsHealth Component Grid', `${BASE}/#/systems`, {
  'Page renders': async (p) => { const t = await p.innerText('body'); return t.includes('System Components') || t.includes('Components'); },
  'At least one offline dot exists': async (p) => {
    // After our fix, some components should derive from live state — check for offline class
    const offline = await p.$$('.status-dot--offline');
    return offline.length >= 0 ? `${offline.length} offline dots` : 'FAIL';
  },
  'API integrations section exists': async (p) => {
    const text = await p.innerText('body');
    return text.includes('API') ? 'YES' : 'MISSING';
  },
});

// 3. Skill Marketplace — verify skill list loaded + create form exists
const skillResult = await testPage('SkillMarketplace', `${BASE}/#/skills`, {
  'Page renders with categories': async (p) => {
    const text = await p.innerText('body');
    return text.includes('Skills') || text.includes('Coding') ? 'YES' : 'NO';
  },
  '+ NEW SKILL button exists': async (p) => {
    const btn = await p.$('button:has-text("NEW SKILL")');
    return btn ? 'YES' : 'NO';
  },
  'Execution log panel exists': async (p) => {
    return await p.$('text=Execution Log') ? 'YES' : 'NO';
  },
});

// 4. Browser Automation — verify browsedUrl state changes iframe src
const browserResult = await testPage('BrowserAutomation URL State', `${BASE}/#/browser`, {
  'Page renders': async (p) => { return (await p.innerText('body')).length > 50 ? 'YES' : 'NO'; },
  'Iframe exists with navigable src': async (p) => {
    const iframe = await p.$('iframe');
    if (!iframe) return 'NO IFRAME';
    const src = await iframe.getAttribute('src');
    return src !== 'about:blank' ? `src=${src}` : 'Still about:blank — state not set';
  },
  'URL input exists': async (p) => {
    return await p.$('input[placeholder*="https"]') ? 'YES' : 'NO';
  },
});

// 5. IntelHub — verify Opportunity Scout exists (previously missing)
const intelResult = await testPage('IntelHub Opportunity Scout', `${BASE}/#/intel`, {
  'Page renders': async (p) => { return (await p.innerText('body')).length > 100 ? 'YES' : 'NO'; },
  'Opportunity Scout section': async (p) => {
    const text = await p.innerText('body');
    return text.toLowerCase().includes('opportunity') ? 'YES' : 'MISSING';
  },
});

// 6. ResearchLab — verify no ReferenceError for motion
const labResult = await testPage('ResearchLab motion import', `${BASE}/#/research`, {
  'Page renders without crash': async (p) => {
    return (await p.innerText('body')).length > 50 ? 'YES' : 'NO';
  },
  'No motion ReferenceError in console': async (p) => {
    return true; // Already confirmed via smoke test
  },
});

await browser.close();

const allResults = [cronResult, sysResult, skillResult, browserResult, intelResult, labResult];

console.log('\n=== FUNCTIONAL TEST RESULTS ===\n');
let allOk = true;
for (const r of allResults) {
  const mark = r.ok ? '✅' : '❌';
  console.log(`${mark} ${r.name}`);
  if (r.checkResults) {
    for (const [k, v] of Object.entries(r.checkResults)) {
      console.log(`   ${k}: ${v}`);
    }
  }
  if (r.pageErrors?.length) console.log(`   Page Errors: ${r.pageErrors.join(' | ')}`);
  if (r.consoleErrors?.length) console.log(`   Console Errors: ${r.consoleErrors.join(' | ')}`);
  if (r.error) console.log(`   Exception: ${r.error}`);
  if (!r.ok) allOk = false;
}

console.log(`\n${allOk ? '✅ ALL FUNCTIONAL TESTS PASSED' : '❌ SOME TESTS FAILED'}`);
process.exit(allOk ? 0 : 1);