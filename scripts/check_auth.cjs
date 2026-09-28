// Read-only browser smoke check: opens login dialogs, never sends email or OAuth.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const assert=require('node:assert/strict');
const origin=process.env.GHOST_PREVIEW_URL||'http://127.0.0.1:8010';
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox'],executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE});
 const page=await browser.newPage({viewport:{width:390,height:844}}),errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 await page.goto(origin+'/auth/login');
 const email=page.getByRole('button',{name:'Continue with email',exact:true});
 await email.waitFor({timeout:60000});
 await email.waitFor({state:'visible'});
 await page.waitForFunction(()=>[...document.querySelectorAll('button')].some(b=>b.textContent.includes('Continue with email')&&!b.disabled),{timeout:30000});
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth),true);
 assert.equal(await page.getByRole('button',{name:'Continue with Google',exact:true}).count(),1);
 await page.screenshot({path:'/tmp/ghost-login-mobile.png',fullPage:true});
 await email.click();
 await page.getByPlaceholder('your@email.com').waitFor({timeout:20000});
 await page.screenshot({path:'/tmp/ghost-email-modal-mobile.png',fullPage:true});
 assert.deepEqual(errors,[]);
 console.log('Passed: real Privy SDK ready, phone login layout, email dialog, no browser errors; no email or OAuth submitted.');
 await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
