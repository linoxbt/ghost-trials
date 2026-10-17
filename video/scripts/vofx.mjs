import {existsSync, mkdirSync, readFileSync, writeFileSync, renameSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {spawnSync} from 'node:child_process';
const script = JSON.parse(readFileSync('script.json', 'utf8'));
let ffmpeg = spawnSync('ffmpeg', ['-version'], {stdio: 'ignore'});
if (ffmpeg.error || ffmpeg.status !== 0) {
  const update = spawnSync('apt-get', ['update'], {stdio: 'inherit'});
  if (update.status !== 0) throw new Error('apt-get update failed');
  const install = spawnSync('apt-get', ['install', '-y', 'ffmpeg'], {stdio: 'inherit'});
  if (install.status !== 0) throw new Error('ffmpeg install failed');
}
mkdirSync('.cache/vofx', {recursive: true});
for (const scene of script.scenes) for (let index = 0; index < scene.lines.length; index++) {
  const stem = `${scene.id}_${index}`;
  const file = `public/audio/vo/${stem}.mp3`;
  if (!existsSync(file)) continue;
  const cache = `.cache/vofx/${stem}.sha`;
  const hash = () => createHash('sha1').update(readFileSync(file)).digest('hex');
  if (existsSync(cache) && readFileSync(cache, 'utf8').trim() === hash()) continue;
  const temp = `public/audio/vo/${stem}.processed.mp3`;
  const result = spawnSync('ffmpeg', ['-y', '-loglevel', 'error', '-i', file, '-af', 'highpass=f=80,loudnorm=I=-16:TP=-1.5:LRA=11', temp], {stdio: 'inherit'});
  if (result.status !== 0) throw new Error(`Voice FX failed for ${stem}`);
  renameSync(temp, file);
  writeFileSync(cache, hash() + '\n');
  console.log(`Voice FX ${stem}: written`);
}
