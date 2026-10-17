import {existsSync, mkdirSync} from 'node:fs';
import {spawnSync} from 'node:child_process';

const cues = {
  tick: {peak: -5, seconds: 0.22},
  thud: {peak: -6, seconds: 1},
  click: {peak: -4, seconds: 0.16},
  slot: {peak: -5, seconds: 0.9},
  chime: {peak: -7, seconds: 1.5},
  pop: {peak: -4, seconds: 0.16},
  whoosh: {peak: -7, seconds: 0.8},
};
mkdirSync('public/audio/design', {recursive: true});
for (const [name, settings] of Object.entries(cues)) {
  const source = `public/audio/sfx/${name}.mp3`;
  if (!existsSync(source)) { console.log(`Design cue skipped: ${name} missing`); continue; }
  const scan = spawnSync('ffmpeg', ['-hide_banner', '-i', source, '-af', 'volumedetect', '-f', 'null', '-'], {encoding: 'utf8'});
  if (scan.status !== 0) throw new Error(`Cannot inspect ${name}`);
  const measured = Number(scan.stderr.match(/max_volume:\s*(-?[\d.]+) dB/)?.[1]);
  if (!Number.isFinite(measured)) throw new Error(`No peak measurement for ${name}`);
  const gain = Math.max(-30, Math.min(26, settings.peak - measured));
  const result = spawnSync('ffmpeg', ['-y', '-hide_banner', '-loglevel', 'error', '-i', source, '-af', `atrim=0:${settings.seconds},volume=${gain.toFixed(2)}dB`, '-ar', '44100', '-ac', '2', '-b:a', '192k', `public/audio/design/${name}.mp3`], {stdio: 'inherit'});
  if (result.status !== 0) throw new Error(`Design cue failed: ${name}`);
  console.log(`Design cue written: ${name}`);
}
