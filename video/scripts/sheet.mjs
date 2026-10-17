import {existsSync, readdirSync} from 'node:fs';
import {spawnSync} from 'node:child_process';
const images = existsSync('out/stills') ? readdirSync('out/stills').filter((file) => file.endsWith('.png')) : [];
if (!images.length) { console.log('Sheet skipped: no stills'); process.exit(0); }
const cols = Math.ceil(Math.sqrt(images.length));
const rows = Math.ceil(images.length / cols);
const result = spawnSync('ffmpeg', ['-y', '-loglevel', 'error', '-pattern_type', 'glob', '-framerate', '1', '-i', 'out/stills/*.png', '-vf', `tile=${cols}x${rows}:padding=20:margin=20`, '-frames:v', '1', 'out/sheet.png'], {stdio: 'inherit'});
if (result.status !== 0) throw new Error('Contact sheet failed');
console.log('Contact sheet written');
