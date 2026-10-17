import {spawnSync} from 'node:child_process';
for (const job of ['data', 'voices', 'voiceover', 'vofx', 'timing', 'music', 'score', 'sfx', 'design-sfx', 'timing', 'capture', 'visuals', 'encode']) {
  const result = spawnSync(process.execPath, [`scripts/${job}.mjs`], {stdio: 'inherit'});
  if (result.status !== 0) throw new Error(`Finish stopped at ${job}`);
}
console.log('Finish complete');
