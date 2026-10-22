// Customer workspace fixtures exercise the UI only; no real identity is created.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const assert=require('node:assert/strict');
const origin=process.env.GHOST_PREVIEW_URL||'http://127.0.0.1:8012';
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox'],executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE});
 const page=await browser.newPage({viewport:{width:390,height:844}}),errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 const reply=(route,data)=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(data)});
 const id='org_fixture',subject='did:privy:fixture-owner';
 await page.route('**/account',r=>reply(r,{subject,role:'admin',authentication_kind:'privy',active_organization_id:id,
   organizations:[{id,name:'Warehouse safety team',role:'admin'}]}));
 await page.route('**/organizations/current',r=>reply(r,{id,name:'Warehouse safety team',owner:subject,
   budget:{limit_cents:5000,used_cents:1200},members:[{subject,display_name:'Owner',role:'admin'},
     {subject:'did:privy:fixture-member',display_name:'Teammate',role:'viewer'}]}));
 await page.route('**/organizations/current/audit',r=>reply(r,[{at:Date.now()/1000,subject,action:'member_invited',role:'admin'}]));
 await page.route('**/organizations/current/invitations',r=>reply(r,{accept_url:'/auth/invite#ui-test-only-not-a-real-invite'}));
 let change;
 await page.route('**/organizations/current/members/*',r=>{change=r.request().postDataJSON();return reply(r,{status:'updated'});});
 await page.goto(origin+'/app/#/team');
 await page.getByRole('heading',{name:'Workspace members',exact:true}).waitFor();
 await page.getByRole('button',{name:'Create invitation link'}).click();
 await page.waitForFunction(()=>document.getElementById('inviteLink')?.value);
 assert.equal(await page.getByLabel('Invitation link').inputValue(),origin+'/auth/invite#ui-test-only-not-a-real-invite');
 await page.getByLabel('Role for did:privy:fixture-member').selectOption('operator');
 await page.waitForFunction(()=>document.getElementById('toast').textContent.includes('permissions updated'));
 assert.equal(change.role,'operator');
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,'Team view overflow');
 await page.screenshot({path:'/tmp/ghost-team-mobile.png',fullPage:true});
 await page.setViewportSize({width:1440,height:1000});
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
 assert.deepEqual(errors,[]);
 await browser.close();
 console.log('Passed: customer UI fixtures, team roles, invitation link, audit view, phone and desktop layout. Real auth separately verified by API tests; no provider signup performed.');
})().catch(error=>{console.error(error);process.exit(1)});
