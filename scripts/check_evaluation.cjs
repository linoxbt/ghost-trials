const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const assert=require('node:assert/strict');
const origin=(process.env.GHOST_PREVIEW_URL||'http://127.0.0.1:8010').replace(/\/$/,'');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox'],executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1000}});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  const records=await (await page.request.get(origin+'/trials')).json();
  assert.ok(records.length>=2,'Use a populated development or fixture workspace.');
  await page.goto(origin+'/app/#/compare');
  await page.getByRole('heading',{name:'Measured differences'}).waitFor();
  assert.equal(await page.getByRole('button',{name:'Play both recordings'}).isDisabled(),true);
  await page.getByRole('heading',{name:'Exploratory comparison only'}).waitFor();
  const download=page.waitForEvent('download');await page.getByRole('button',{name:'Export comparison'}).click();
  assert.match((await download).suggestedFilename(),/^comparison-/);
  const chosen=await page.locator('#baselineTrial').inputValue();
  await page.locator('#candidateTrial').selectOption(chosen);
  await page.getByText('Choose two different trials.',{exact:true}).waitFor();
  await page.reload();await page.getByText('Choose two different trials.',{exact:true}).waitFor();
  await page.goto(origin+'/app/#/benchmarks');
  await page.getByRole('heading',{name:'Execution scope'}).waitFor();
  assert.ok(await page.locator('.coverage-card').count()>0);
  await page.screenshot({path:'/tmp/ghost-benchmarks-desktop.png',fullPage:true});
  await page.goto(origin+'/app/#/trials/'+records[0].trial_id);
  await page.getByRole('heading',{name:'Incident timeline'}).waitFor();
  await page.getByText('No timestamped telemetry events were captured for this record.',{exact:false}).waitFor();
  const evidenceDownload=page.waitForEvent('download');await page.getByRole('button',{name:'Export evidence assessment'}).click();
  assert.match((await evidenceDownload).suggestedFilename(),/-reproducibility.json$/);
  if((await (await page.request.get(origin+'/health')).json()).mode==='local'){
   const originalId=records[0].trial_id;
   await page.getByRole('button',{name:'Replay demo scenario'}).click();
   await page.waitForURL(url=>url.hash.startsWith('#/trials/')&&!url.hash.endsWith(originalId));
   await page.getByRole('button',{name:'Replay demo scenario'}).waitFor();
   const replayId=page.url().split('/').at(-1);
   const replay=await (await page.request.get(origin+'/trials/'+replayId)).json();
   assert.equal(replay.replay_of,originalId);
   assert.equal(replay.scenario_id,records[0].scenario_id);
  }
  for(const width of [320,390,768,1440]){
   await page.setViewportSize({width,height:900});
   for(const [path,ready] of [['compare','Measured differences'],['benchmarks','Execution scope'],['trials/'+records[0].trial_id,'Incident timeline']]){
    await page.goto(origin+'/app/#/'+path);await page.getByRole('heading',{name:ready,exact:true}).waitFor();
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,`${path} overflow at ${width}`);
   }
  }
  // Network failure must be displayed, not fabricated as a valid comparison.
  await page.route('**/comparisons?*',r=>r.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'Comparison fixture unavailable'})}));
  await page.goto(origin+'/app/#/compare');await page.getByText('Comparison fixture unavailable',{exact:true}).waitFor();
  assert.deepEqual(errors,[]);
  console.log('Passed: comparisons, mismatch guardrails, deep-link reload, benchmark cohorts, evidence export, missing timeline, 320/390/768/1440px layouts, and API error handling.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
