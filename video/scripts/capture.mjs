import {mkdirSync, writeFileSync} from 'node:fs';
import {setTimeout as delay} from 'node:timers/promises';
import {withHeadlessPage} from './cdp.mjs';
import {record} from './status.mjs';
const paths = ['footage/site-1.png', 'footage/site-2.png', 'footage/site-3.png'];
mkdirSync('public/footage', {recursive: true});
const metadata = {width: 1600, height: 900, paths, captured: false};
try {
  await withHeadlessPage(1600, 900, 2, async (cdp) => {
    const navigation = await cdp.send('Page.navigate', {url: 'https://ghost-trials.netlify.app'});
    if (navigation.errorText) throw new Error(navigation.errorText);
    await delay(2500);
    const check = await cdp.send('Runtime.evaluate', {expression: '({title:document.title,text:document.body?.innerText?.slice(0,500),height:document.documentElement.scrollHeight})', returnByValue: true});
    const page = check.result.value;
    if (!page?.text || /ERR_|This site can.t be reached/i.test(page.text)) throw new Error('Site did not load');
    for (let i = 0; i < 3; i++) {
      const y = Math.max(0, Math.round((page.height - 900) * i / 2));
      await cdp.send('Runtime.evaluate', {expression: `window.scrollTo(0, ${y})`});
      await delay(450);
      const screenshot = await cdp.send('Page.captureScreenshot', {format: 'png', captureBeyondViewport: false});
      writeFileSync(`public/${paths[i]}`, Buffer.from(screenshot.data, 'base64'));
    }
    metadata.captured = true;
  });
  record('footage', 'written');
  console.log('Footage: three site screenshots written');
} catch (error) {
  writeFileSync('public/footage/MISSING.txt', `Capture unavailable: ${error.message}\n`);
  record('footage', 'skipped');
  console.log('Footage skipped: site or Chrome unavailable');
}
writeFileSync('src/footage.json', JSON.stringify(metadata, null, 2) + '\n');
