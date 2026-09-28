// Isolated development fixtures only. No GPU, physical robot or paid model calls.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const origin='http://127.0.0.1:8013';
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox'],executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE});
 try{
  const context=await browser.newContext({viewport:{width:390,height:844}});
  const page=await context.newPage(),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  assert.equal((await context.request.post(origin+'/auth/session',{headers:{Origin:origin},data:{token:'a'.repeat(48)}})).status(),200);
  const summary=await (await context.request.get(origin+'/safety-score')).json();
  assert.equal(summary.scored_trials,0);assert.equal(summary.score_available,false);assert.equal(summary.safety_score,null);
  assert.equal(summary.evidence_counts.synthetic_demo,6);
  const records=await (await context.request.get(origin+'/trials')).json();
  assert.ok(records.every(t=>!t.score_eligible&&t.evidence_class==='synthetic_demo'));
  await page.goto(origin+'/app/#/overview');
  await page.getByRole('heading',{name:'Experimental evaluation platform — not safety certification'}).waitFor();
  await page.getByText('Real-trial milestone: pending actual policy execution',{exact:true}).waitFor();
  assert.equal(await page.locator('.stat-value').first().innerText(),'—');
  await page.goto(origin+'/app/#/trials');
  await page.getByLabel('Filter evidence provenance').waitFor();
  await page.getByLabel('Filter evidence provenance').selectOption('eligible');
  await page.getByRole('heading',{name:'No matching trials'}).waitFor();
  await page.getByLabel('Filter evidence provenance').selectOption('synthetic_demo');
  assert.equal(await page.locator('.data-table tbody tr').count(),6);
  await page.goto(origin+'/app/#/trials/'+records[0].trial_id);
  await page.getByRole('heading',{name:'SYNTHETIC DEMO · NO ROBOT RUN',exact:true}).waitFor();
  await page.getByText('Excluded from the evaluation score.',{exact:false}).waitFor();
  const downloaded=page.waitForEvent('download');
  await page.getByRole('button',{name:'Export record',exact:true}).click();
  const download=await downloaded;
  assert.match(download.suggestedFilename(),/-reproducibility.json$/);
  const exported=JSON.parse(fs.readFileSync(await download.path(),'utf8'));
  assert.equal(exported.certification,false);assert.equal(exported.evidence.score_eligible,false);
  assert.equal(exported.configuration.seed,records[0].scenario.seed);
  assert.ok(exported.artifacts&&exported.limitations.length);
  for(const width of [320,390,1440]){
   await page.setViewportSize({width,height:900});
   for(const route of ['overview','trials','trials/'+records[0].trial_id,'reports']){
    await page.goto(origin+'/app/#/'+route);await page.locator('#content h1').waitFor();
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`${route} overflow at ${width}`);
   }
  }
  await page.setViewportSize({width:390,height:844});await page.goto(origin+'/app/#/overview');
  await page.getByText('Real-trial milestone: pending actual policy execution',{exact:true}).waitFor();
  await page.screenshot({path:'/tmp/ghost-evidence-overview-mobile.png',fullPage:true});
  assert.deepEqual(errors,[]);
  console.log('Passed: fixture exclusion, null score, pending real execution, evidence filters/labels, reproducibility download, and 320/390/1440px layout. No paid provider or hardware used.');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exit(1);});
