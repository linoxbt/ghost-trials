import {mkdirSync} from 'node:fs';
import {spawnSync} from 'node:child_process';
const frames = process.argv.slice(2).map(Number);
if (!frames.length || frames.some((frame) => !Number.isInteger(frame) || frame < 0)) throw new Error('Usage: node scripts/stills.mjs 0 90 180');
mkdirSync('out/stills', {recursive: true});
for (const frame of frames) {
  const result = spawnSync('npx', ['remotion', 'still', 'GhostTrials', `out/stills/${frame}.png`, '--frame', String(frame), '--scale', '0.5', '--concurrency', '1'], {stdio: 'inherit'});
  if (result.status !== 0) throw new Error(`Still frame ${frame} failed`);
}
