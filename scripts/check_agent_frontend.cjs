// Optional real-browser smoke: PLAYWRIGHT_MODULE=/path/to/playwright node scripts/check_agent_frontend.cjs
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const {spawn} = require('node:child_process');
const {mkdtempSync} = require('node:fs');
const {tmpdir} = require('node:os');
const {join} = require('node:path');
const assert = require('node:assert/strict');

async function main(){
  const root=mkdtempSync(join(tmpdir(),'ghost-agent-ui-'));
  const server=spawn('uv',['run','python','-m','scripts.run_cpu','--port','8765'],{
    cwd:join(__dirname,'..'),detached:true,stdio:['ignore','pipe','pipe'],env:{...process.env,
      GHOST_DATA_PATH:join(root,'state.sqlite3'),GHOST_ARTIFACT_ROOT:join(root,'artifacts'),
      GHOST_CUSTOMER_AUTH_REQUIRED:'false',PRIVY_APP_ID:'',NEBIUS_API_KEY:'',
      GHOST_CPU_MODEL_REVIEW_ENABLED:'false'}});
  let browser,logs='';
  server.stdout.on('data',chunk=>logs+=chunk.toString());
  server.stderr.on('data',chunk=>logs+=chunk.toString());
  try{
    let ready=false;
    for(let i=0;i<100;i++){
      if(server.exitCode!==null)throw Error('CPU server exited before readiness');
      try{ready=(await fetch('http://127.0.0.1:8765/health')).ok;}catch{}
      if(ready)break;
      await new Promise(r=>setTimeout(r,100));
    }
    if(!ready)throw Error('CPU server did not become ready: '+logs.slice(-1200));
    browser=await chromium.launch({headless:true,args:['--no-sandbox'],
      executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE||'/usr/bin/google-chrome'});
    const page=await browser.newPage({viewport:{width:390,height:844}});
    const errors=[];page.on('pageerror',e=>errors.push(e.message));
    assert.equal((await page.request.get('http://127.0.0.1:8765/docs/agent')).status(),200);
    await page.goto('http://127.0.0.1:8765/docs');
    await page.getByRole('heading',{name:'AI-agent software verification'}).waitFor();
    await page.locator('#docsSearch').fill('agent');
    assert.equal(await page.locator('.docs-sidebar a[href="/docs/agent"]').isVisible(),true);
    await page.goto('http://127.0.0.1:8765/');
    await page.getByRole('heading',{name:'Challenge a robot controller.'}).waitFor();
    await page.getByRole('heading',{name:"Challenge an agent's boundaries."}).waitFor();
    await page.getByRole('link',{name:'Start an AI Agent Hunt'}).click();
    await page.waitForURL('**/app/#/hunt?domain=ai_agent');
    await page.locator('#huntDomain').waitFor();
    assert.equal(await page.locator('#huntDomain').inputValue(),'ai_agent');
    assert.equal(await page.locator('#agentHuntForm').isVisible(),true);
    assert.equal(await page.locator('#huntForm').isVisible(),false);
    await page.locator('#agentHuntForm [name=max_trials]').fill('6');
    await page.locator('#agentHuntForm button[type=submit]').click();
    await page.waitForURL('**/#/hunt/hunt_*');
    await page.getByText('VERIFIED FAILURE FOUND').waitFor({timeout:30000});
    await page.getByRole('link',{name:/Inspect trace/}).first().click();
    await page.getByRole('heading',{name:'Deterministic assertions'}).waitFor();
    assert.equal(await page.getByRole('button',{name:'Request budgeted model review'}).isDisabled(),true);
    await page.goto('http://127.0.0.1:8765/app/#/failures');
    await page.locator('.hunt-list-item').first().click();
    await page.getByText('DETERMINISTIC ORACLE').waitFor();
    await page.getByRole('button',{name:'Test corrected agent'}).click();
    await page.getByText('verified success').waitFor();
    assert.deepEqual(errors,[]);
    console.log('Browser passed: mobile agent Hunt, real trace, Ghost Case, corrected-agent regression.');
  }finally{
    if(browser)await browser.close();
    try{process.kill(-server.pid,'SIGTERM');}catch{}
  }
}
main().catch(e=>{console.error(e);process.exitCode=1;});
