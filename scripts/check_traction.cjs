// Creates one clearly synthetic local trial; never run against production providers.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const assert=require('node:assert/strict');
const origin=process.env.GHOST_PREVIEW_URL||'http://127.0.0.1:8010';
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox'],executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE});
 try{
  const page=await browser.newPage();const errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  assert.equal((await (await page.request.get(origin+'/health')).json()).mode,'local');
  await page.goto(origin+'/app/#/new?template=1');
  await page.getByLabel('Hazard description').waitFor();
  assert.match(await page.getByLabel('Hazard description').inputValue(),/slippery/);
  await page.getByRole('button',{name:'Create demo trial'}).click();
  await page.waitForURL('**/#/trials/*');
  await page.getByText('Contact slip target',{exact:true}).waitFor();
  const id=page.url().split('/').at(-1);
  let trial;
  for(let attempt=0;attempt<60;attempt++){
   trial=await (await page.request.get(origin+'/trials/'+id)).json();
   if(['done','error'].includes(trial.status))break;
   await page.waitForTimeout(250);
  }
  assert.equal(trial.status,'done');
  assert.equal(trial.metrics.min_clearance_m,null);
  assert.equal(trial.metrics.evidence_origin,'synthetic');
  assert.ok(trial.metrics.max_contact_slip_speed_m_s>=0);
  for(const width of [320,390,1440]){
   await page.setViewportSize({width,height:900});
   await page.reload();await page.getByText('Contact slip target',{exact:true}).waitFor();
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
  }
  assert.deepEqual(errors,[]);
  console.log('Passed: reduced-traction template, synthetic labeling, nullable clearance, slip threshold, reload and mobile layout.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
