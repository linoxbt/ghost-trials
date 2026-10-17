import {existsSync, mkdirSync} from 'node:fs';
import {spawnSync} from 'node:child_process';

const crops = [
  ['site-1.png', 'hero-copy.png', 'crop=1500:1160:90:215'],
  ['site-2.png', 'site-cards.png', 'crop=2970:530:140:0'],
  ['site-2.png', 'pipeline.png', 'crop=3100:1040:50:710'],
  ['site-3.png', 'cta.png', 'crop=2900:820:140:580'],
];
mkdirSync('public/footage/crops', {recursive: true});
for (const [source, name, filter] of crops) {
  const input = `public/footage/${source}`;
  if (!existsSync(input)) { console.log(`Visual crop skipped: ${source} missing`); continue; }
  const result = spawnSync('ffmpeg', ['-hide_banner', '-loglevel', 'error', '-y', '-i', input, '-vf', filter, `public/footage/crops/${name}`], {stdio: 'inherit'});
  if (result.status !== 0) throw new Error(`Visual crop failed: ${name}`);
  console.log(`Visual crop written: ${name}`);
}
