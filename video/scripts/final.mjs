import {existsSync, writeFileSync} from 'node:fs';
import {spawnSync} from 'node:child_process';
const input = 'out/ghost-trials-1080p.mp4';
if (!existsSync(input)) throw new Error('1080p render is missing');
const probe = spawnSync('ffprobe', ['-v', 'error', '-select_streams', 'a', '-show_entries', 'stream=index', '-of', 'csv=p=0', input], {encoding: 'utf8'});
if (probe.status !== 0) throw new Error('ffprobe failed');
if (!probe.stdout.trim()) {
  writeFileSync('out/loudness.json', JSON.stringify({status: 'no audio stream'}, null, 2) + '\n');
  console.log('Loudness: no audio stream');
  process.exit(0);
}
const measure = spawnSync('ffmpeg', ['-hide_banner', '-i', input, '-af', 'loudnorm=I=-14:TP=-1:LRA=11:print_format=json', '-f', 'null', '-'], {encoding: 'utf8'});
if (measure.status !== 0) throw new Error('Loudness measurement failed');
const match = measure.stderr.match(/\{\s*"input_i"[\s\S]*?\}/);
if (!match) throw new Error('No loudnorm measurements found');
const loudness = JSON.parse(match[0]);
writeFileSync('out/loudness.json', JSON.stringify(loudness, null, 2) + '\n');
if (Number(loudness.input_i) > -13.5 || Number(loudness.input_i) < -14.8 || Number(loudness.input_tp) > -1) {
  const corrected = spawnSync('ffmpeg', ['-y', '-loglevel', 'error', '-i', input, '-c:v', 'copy', '-af', 'loudnorm=I=-14:TP=-1:LRA=11', '-c:a', 'aac', '-b:a', '320k', 'out/ghost-trials-1080p-broadcast.mp4'], {stdio: 'inherit'});
  if (corrected.status !== 0) throw new Error('Broadcast correction failed');
  console.log('Broadcast correction written');
} else console.log('Loudness: within target');
