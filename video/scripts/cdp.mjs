import {spawn} from 'node:child_process';
import {existsSync, mkdtempSync, readFileSync, rmSync} from 'node:fs';
import {setTimeout as delay} from 'node:timers/promises';
const browserPath = 'node_modules/.remotion/chrome-headless-shell/linux64/chrome-headless-shell-linux64/chrome-headless-shell';

class Connection {
  constructor(ws) {
    this.ws = ws; this.nextId = 1; this.pending = new Map();
    ws.addEventListener('message', (event) => {
      const message = JSON.parse(event.data);
      const pending = this.pending.get(message.id);
      if (!pending) return;
      this.pending.delete(message.id);
      if (message.error) pending.reject(new Error(message.error.message));
      else pending.resolve(message.result);
    });
  }
  send(method, params = {}) {
    const id = this.nextId++;
    return new Promise((resolve, reject) => {
      this.pending.set(id, {resolve, reject});
      this.ws.send(JSON.stringify({id, method, params}));
    });
  }
  close() { this.ws.close(); }
}

export const withHeadlessPage = async (width, height, deviceScaleFactor, task) => {
  if (!existsSync(browserPath)) throw new Error('Remotion Chrome Headless Shell is missing');
  const profile = mkdtempSync('.cache/cdp-');
  const child = spawn(browserPath, ['--headless=new', '--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage', '--remote-debugging-port=0', `--user-data-dir=${profile}`, 'about:blank'], {stdio: 'ignore'});
  let connection;
  try {
    const portFile = `${profile}/DevToolsActivePort`;
    for (let i = 0; i < 100 && !existsSync(portFile); i++) await delay(100);
    if (!existsSync(portFile)) throw new Error('Chrome debugging port did not open');
    const port = Number(readFileSync(portFile, 'utf8').split('\n')[0]);
    const targetResponse = await fetch(`http://127.0.0.1:${port}/json/new?about:blank`, {method: 'PUT'});
    if (!targetResponse.ok) throw new Error(`Chrome target HTTP ${targetResponse.status}`);
    const target = await targetResponse.json();
    const ws = new WebSocket(target.webSocketDebuggerUrl);
    await new Promise((resolve, reject) => { ws.addEventListener('open', resolve, {once: true}); ws.addEventListener('error', reject, {once: true}); });
    connection = new Connection(ws);
    await connection.send('Page.enable');
    await connection.send('Runtime.enable');
    await connection.send('Emulation.setDeviceMetricsOverride', {width, height, deviceScaleFactor, mobile: false});
    return await task(connection);
  } finally {
    connection?.close();
    child.kill('SIGTERM');
    await delay(300);
    rmSync(profile, {recursive: true, force: true});
  }
};
if (process.argv[1]?.endsWith('/cdp.mjs')) console.log('CDP client ready: import withHeadlessPage(width, height, deviceScaleFactor, task)');
