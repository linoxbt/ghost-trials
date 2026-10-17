import {existsSync} from 'node:fs';
import {spawnSync} from 'node:child_process';
if (![1, 2, 3].every((n) => existsSync(`public/footage/site-${n}.png`))) { console.log('Encode skipped: site screenshots missing'); process.exit(0); }
const result = spawnSync('ffmpeg', ['-y', '-loglevel', 'error', '-framerate', '2', '-i', 'public/footage/site-%d.png', '-vf', 'scale=1600:900', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', 'public/footage/site.mp4'], {stdio: 'inherit'});
if (result.status !== 0) throw new Error('Footage encoding failed');
console.log('Footage video written');
