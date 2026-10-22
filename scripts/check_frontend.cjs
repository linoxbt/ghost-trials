// Run with PLAYWRIGHT_MODULE set to an installed Playwright package if needed.
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict');
const origin = process.env.GHOST_PREVIEW_URL || 'http://127.0.0.1:8000';
const base = origin.replace(/\/$/,'')+'/app';
(async () => {
  const browser = await chromium.launch({headless:true, args:['--no-sandbox'], executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE});
  const page = await browser.newPage({viewport:{width:1440,height:1060}});
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto(base+'/');
  await page.getByRole('heading',{name:'Ghost Trials',exact:true}).waitFor();
  assert.equal((await (await page.request.get(origin+'/health')).json()).mode,'local','Run this check against a development workspace; it creates a synthetic trial.');
  await page.screenshot({path:'/tmp/ghost-overview-desktop.png',fullPage:true});
  await page.getByRole('navigation').getByRole('link',{name:'Trials'}).click();
  await page.getByLabel('Search trials').fill('no-matching-record-987');
  await page.getByRole('heading',{name:'No matching trials'}).waitFor();
  await page.getByRole('button',{name:'Clear filters'}).click();
  await page.locator('.trial-link').first().waitFor();
  await page.getByLabel('Filter severity').selectOption('high');
  const rows = await page.locator('.data-table tbody tr').all();
  for(const row of rows) assert.equal(await row.locator('td').nth(1).innerText(),'High');
  await page.goto(base+'/#/scenarios');
  await page.getByRole('link',{name:'Use template'}).first().click();
  assert.match(await page.getByLabel('Hazard description').inputValue(),/box slips/);
  await page.getByLabel('Scenario seed').fill('773');
  await page.getByRole('heading',{name:'This creates a demo record, not an AI video.'}).waitFor();
  await page.getByRole('button',{name:'Create demo trial'}).click();
  await page.waitForURL('**/#/trials/*');
  await page.locator('.detail-heading .badge').filter({hasText:/avoided|mitigated|failed|catastrophic/}).waitFor({timeout:30000});
  const trialUrl = page.url();
  const downloadWait = page.waitForEvent('download');
  await page.getByRole('button',{name:'Export record'}).click();
  const download = await downloadWait;
  assert.match(download.suggestedFilename(),/^trl_.*\.json$/);
  await page.reload();
  await page.getByRole('heading',{name:'Auditor finding'}).waitFor();
  await page.goto(base+'/#/reports');
  await page.getByRole('heading',{name:'Reports & evidence'}).waitFor();
  const allDownload = page.waitForEvent('download');
  await page.getByRole('button',{name:'Export evaluation'}).click();
  assert.equal((await allDownload).suggestedFilename(),'ghost-trials-evaluation.json');
  await page.goto(base+'/#/new');
  await page.getByLabel('Hazard description').fill('A box falls from the shelf while the robot approaches.');
  // Live refresh must not discard an in-progress form.
  await page.evaluate(()=>refresh());
  assert.match(await page.getByLabel('Hazard description').inputValue(),/box falls/);
  await page.route('**/scenarios',route=>route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'Test provider unavailable'})}));
  await page.getByRole('button',{name:'Create demo trial'}).click();
  await page.getByText('Test provider unavailable',{exact:true}).waitFor();
  assert.equal(await page.getByRole('button',{name:'Create demo trial'}).isEnabled(),true);
  await page.unroute('**/scenarios');
  await page.setViewportSize({width:390,height:844});
  await page.goto(base+'/#/overview');
  await page.getByRole('heading',{name:'Ghost Trials',exact:true}).waitFor();
  await page.locator('#toast').evaluate(el=>el.hidden=true);
  assert.equal(await page.locator('#sidebar').evaluate(el=>el.inert),true);
  await page.getByRole('button',{name:'Toggle navigation'}).click();
  assert.equal(await page.locator('#menuButton').getAttribute('aria-expanded'),'true');
  await page.screenshot({path:'/tmp/ghost-mobile-menu.png',fullPage:true});
  await page.keyboard.press('Escape');
  assert.equal(await page.getByRole('button',{name:'Toggle navigation'}).getAttribute('aria-expanded'),'false');
  assert.equal(await page.locator('#menuButton').evaluate(el=>el===document.activeElement),true);
  for(const [path,name] of [['overview','Ghost Trials'],['hunt','Release the Ghost'],['failures','Failure library'],['trials','Trial runs'],['scenarios','Scenario library'],['reports','Reports & evidence'],['account','Account'],['new','Create a trial']]){
    await page.goto(base+'/#/'+path);
    await page.getByRole('heading',{name,exact:path==='overview'||path==='trials'||path==='account'}).waitFor();
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth),true,`${path}: horizontal page overflow`);
    if(['overview','trials','scenarios','reports'].includes(path)){
      for(const record of await page.locator('.data-table tbody tr').all()){
        const rect=await record.boundingBox();
        assert.ok(rect.x>=0&&rect.x+rect.width<=390,`${path}: phone record needs horizontal scrolling`);
        const action=await record.locator('td').last().boundingBox();
        assert.ok(action.width>200,`${path}: full-width mobile action missing`);
      }
    }
  }
  await page.goto(trialUrl);
  await page.getByRole('heading',{name:'Auditor finding'}).waitFor();
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth),true,'detail overflow');
  await page.goto(base+'/#/overview');
  await page.getByRole('heading',{name:'Ghost Trials',exact:true}).waitFor();
  await page.screenshot({path:'/tmp/ghost-overview-mobile.png',fullPage:true});
  await page.getByRole('button',{name:'Toggle navigation'}).click();
  await page.getByRole('navigation').getByRole('link',{name:'Trials'}).click();
  await page.getByRole('heading',{name:'Trial runs',exact:true}).waitFor();
  assert.equal(await page.locator('#sidebar').evaluate(el=>el.inert),true);
  for(const width of [320,768,1280]){
    await page.setViewportSize({width,height:900});
    await page.goto(base+'/#/overview');
    await page.getByRole('heading',{name:'Ghost Trials',exact:true}).waitFor();
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth),true,`Overview overflow at ${width}px`);
  }
  assert.deepEqual(errors,[]);
  await browser.close();
  console.log('Passed: routing, filters, trial creation, live updates, evidence exports, provider error, mobile navigation, Escape/focus, and seven responsive views.');
})().catch(e=>{console.error(e);process.exit(1)});
