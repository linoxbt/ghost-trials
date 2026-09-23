const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const assert=require('node:assert/strict');
const base=process.env.GHOST_PREVIEW_URL||'http://127.0.0.1:8010';
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox'],executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE});
 const page=await browser.newPage({viewport:{width:1440,height:1000}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(base,{waitUntil:'networkidle'});
 await page.getByRole('heading',{name:'Find the failure. Before the world does.'}).waitFor();
 const first=await page.locator('#world').evaluate(c=>c.toDataURL());
 await page.getByRole('button',{name:'02 / Obstruction'}).click();
 assert.equal(await page.locator('#hazardName').textContent(),'PATH OBSTRUCTION');
 assert.notEqual(await page.locator('#world').evaluate(c=>c.toDataURL()),first);
 await page.getByRole('button',{name:'Pause illustration'}).click();
 await page.getByRole('button',{name:'Play illustration'}).waitFor();
 await page.screenshot({path:'/tmp/ghost-landing-desktop.png',fullPage:false,animations:'disabled'});
 await page.getByRole('link',{name:'Documentation',exact:true}).click();
 await page.getByRole('heading',{name:'From first trial to reviewable evidence.'}).waitFor();
 await page.getByPlaceholder('Search documentation…').fill('Cosmos');
 assert.ok(await page.locator('.docs-sidebar nav a:visible').count()>0);
 await page.getByRole('button',{name:'Copy',exact:true}).first().click();
 await page.getByRole('button',{name:/Copied|Select to copy/}).waitFor();
 await page.screenshot({path:'/tmp/ghost-docs-desktop.png',fullPage:false,animations:'disabled'});
 await page.goto(base+'/#/new');
 await page.waitForURL('**/app/#/new');
 await page.getByRole('heading',{name:'This creates a demo record, not an AI video.'}).waitFor();
 await page.locator('.generation-notice summary').click();
 await page.getByText('Cosmos endpoint',{exact:true}).waitFor();
 for(const width of [390,320]){
  await page.setViewportSize({width,height:844});
  for(const path of ['/','/docs','/app/#/new']){
   await page.goto(base+path);await page.locator('h1').waitFor();
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,`${width}: overflow at ${path}`);
  }
 }
 await page.setViewportSize({width:390,height:844});await page.goto(base);
 await page.getByRole('button',{name:'Toggle menu'}).click();
 await page.getByRole('navigation',{name:'Main navigation'}).getByRole('link',{name:'Documentation'}).click();
 await page.waitForURL('**/docs');
 await page.goto(base);await page.locator('#world').waitFor();
 await page.screenshot({path:'/tmp/ghost-landing-mobile.png',fullPage:true,animations:'disabled'});
 const reduced=await browser.newPage({reducedMotion:'reduce'});await reduced.goto(base);await reduced.getByRole('button',{name:'Play illustration'}).waitFor();
 assert.equal(await reduced.locator('.reveal').first().evaluate(e=>getComputedStyle(e).opacity),'1');
 assert.deepEqual(errors,[]);await browser.close();console.log('Passed: landing motion controls, hazard switching, docs search/copy, legacy links, honest generation notice, mobile navigation, 320px layouts, reduced motion.');
})().catch(e=>{console.error(e);process.exit(1)});
