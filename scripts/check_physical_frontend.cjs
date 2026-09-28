// Isolated-server browser checks. The uploaded orange clip is a test fixture,
// not robot footage. Never point this mutating test at a customer deployment.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const origin=process.env.GHOST_TEST_ORIGIN||'http://127.0.0.1:8012';
if(!/^http:\/\/127\.0\.0\.1:8012$/.test(origin))throw new Error('Use the isolated local test server only');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox'],executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE});
 const context=await browser.newContext({viewport:{width:390,height:844}}),page=await context.newPage(),errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 const response=await context.request.post(origin+'/auth/session',{headers:{Origin:origin},data:{token:'a'.repeat(48)}});
 assert.equal(response.status(),200); // API client follows the redirect to the workspace.
 await page.goto(origin+'/app/#/physical');
 await page.getByRole('heading',{name:'Physical recordings',exact:true}).waitFor();
 await page.getByLabel('Supervised task description').fill('UI fixture only: observe an approved low-risk task.');
 await page.getByLabel('Policy name',{exact:true}).fill('browser-fixture-policy');
 await page.getByRole('button',{name:'Prepare session',exact:true}).click();
 await page.locator('[data-session]').first().waitFor();
 await page.waitForFunction(()=>document.querySelector('.physical-session')?.innerText.includes('Waiting for hardware access'));
 assert.match(await page.locator('[data-session]').first().innerText(),/Waiting for hardware access/);
 const download=page.waitForEvent('download');await page.getByRole('button',{name:'Download setup'}).first().click();
 assert.match((await download).suggestedFilename(),/^phy_.*-setup\.json$/);
 await page.getByRole('button',{name:'Edit setup'}).first().click();
 await page.getByLabel('Robot serial (when available)').fill('browser-fixture-not-a-robot');
 await page.getByLabel('Hardware compatibility').selectOption('g1_29dof');
 await page.getByLabel('Policy checkpoint digest (when available)').fill('sha256:'+'a'.repeat(64));
 await page.locator('#physicalOperator').check();
 await page.getByRole('button',{name:'Save capture setup'}).click();
 await page.getByRole('button',{name:'Prepare session',exact:true}).waitFor();
 await page.waitForFunction(()=>document.querySelector('.physical-session')?.innerText.includes('browser-fixture-not-a-robot'));
 const metadata={schema_version:'g1-readonly-recording-v1',robot_serial:'browser-fixture-not-a-robot',robot_variant:'g1_29dof',
  checkpoint_digest:'sha256:'+'a'.repeat(64),controller_name:'browser-fixture-policy',observer_only:true,
  operator_confirmed_physical_hardware:true,clock_basis:'capture_host_monotonic',video_offset_ms:0,
  video_sync_uncertainty_ms:50,command_change_threshold_rad:.03,clearance_method:null,calibration_id:null};
 const rows=Array.from({length:11},(_,i)=>({timestamp_ms:i*100,state_age_ms:0,command_age_ms:0,
  joint_positions_rad:Array(29).fill(0),imu_rpy_rad:[0,0,0],policy_command_rad:i>=2?[.1,...Array(28).fill(0)]:Array(29).fill(0),
  hazard_active:i>=1,task_completed:i===10,collision_observed:false,fall_observed:false,intervention_active:false,clearance_m:null}));
 await page.locator('[data-files]').first().setInputFiles([
  {name:'response.mp4',mimeType:'video/mp4',buffer:fs.readFileSync(process.env.GHOST_FIXTURE_VIDEO)},
  {name:'capture.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(metadata))},
  {name:'telemetry.jsonl',mimeType:'application/octet-stream',buffer:Buffer.from(rows.map(r=>JSON.stringify(r)).join('\n')+'\n')}
 ]);
 await page.locator('.physical-session').first().getByRole('link',{name:'Inspect flight record ↗'}).waitFor({timeout:60000});
 await page.locator('.physical-session').first().getByRole('link',{name:'Inspect flight record ↗'}).click();
 await page.getByRole('heading',{name:'Auditor finding'}).waitFor();
 assert.match(await page.locator('.finding').first().innerText(),/No judge has run/);
 assert.equal(await page.getByRole('button',{name:/Replay/}).count(),0);
 await page.getByRole('heading',{name:'Evidence inspector'}).waitFor();
 const camera=page.locator('video[aria-label="Robot policy response"]');
 await camera.evaluate(video=>video.play());
 await page.waitForFunction(()=>{const video=document.querySelector('video');return video?.readyState>=2&&video.videoWidth===64;});
 await camera.evaluate(video=>video.pause());
 await page.screenshot({path:'/tmp/ghost-physical-record-mobile.png',fullPage:true});
 for(const width of [320,390,1440]){
  await page.setViewportSize({width,height:900});await page.goto(origin+'/app/#/physical');
  await page.getByRole('heading',{name:'Physical recordings',exact:true}).waitFor();
  await page.getByRole('link',{name:'Inspect flight record ↗'}).first().waitFor();
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,`Physical view overflow at ${width}px`);
 }
 await page.screenshot({path:'/tmp/ghost-physical-desktop.png',fullPage:true});
 assert.deepEqual(errors,[]);await context.close();await browser.close();
 console.log('Passed: physical capture plan, pending access, setup edit/download, fixture upload/video validation, unscored flight record, and mobile/desktop layout. NO hardware or paid model used.');
})().catch(e=>{console.error(e);process.exit(1)});
