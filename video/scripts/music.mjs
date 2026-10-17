import {existsSync, mkdirSync, readFileSync, writeFileSync} from 'node:fs';
import {spawnSync} from 'node:child_process';
import {key} from './env.mjs';
import {record} from './status.mjs';
if (!key) { record('music', 'skipped: missing key'); console.log('Music skipped: missing key'); process.exit(0); }
const output = 'public/audio/music.mp3';
if (existsSync(output) && process.env.FORCE !== '1') { record('music', 'written: cached'); console.log('Music: cached'); process.exit(0); }
const timing = JSON.parse(readFileSync('src/timing.json', 'utf8'));
const musicLengthMs = Math.max(20000, Math.min(120000, Math.round(timing.totalFrames / 30 * 1000)));
let response;
try {
  response = await fetch('https://api.elevenlabs.io/v1/music', {
    method: 'POST', headers: {'xi-api-key': key, 'Content-Type': 'application/json', Accept: 'audio/mpeg, application/json'},
    body: JSON.stringify({prompt: 'very quiet felt piano, soft low pulse, no drums, no vocals, cold documentary', music_length_ms: musicLengthMs, force_instrumental: true}),
  });
} catch (error) { record('music', `skipped: ${error.cause?.code ?? error.name}`); console.log('Music skipped: network unavailable'); process.exit(0); }
if ([401, 404, 429].includes(response.status)) { record('music', `skipped: HTTP ${response.status}`); console.log(`Music skipped: HTTP ${response.status}`); process.exit(0); }
if (response.status !== 402 && !response.ok) throw new Error(`Music HTTP ${response.status}`);
mkdirSync('public/audio', {recursive: true});
if (response.ok) {
  let audio;
  if (response.headers.get('content-type')?.includes('json')) {
    const body = await response.json();
    const base64 = body.audio_base64 ?? body.audio ?? body.base64_audio;
    if (!base64) throw new Error('Music response has no audio');
    audio = Buffer.from(base64, 'base64');
  } else audio = Buffer.from(await response.arrayBuffer());
  writeFileSync(output, audio);
  record('music', 'written: Music API');
  console.log('Music written from Music API');
  process.exit(0);
}

console.log('Music API HTTP 402; creating a score from sound-generation beds');
mkdirSync('.cache/music', {recursive: true});
const beds = [
  ['air', 'Twenty six second cold documentary ambience. Quiet airy room tone, distant resonant tones, no percussion, no voices, seamless restrained texture.'],
  ['pulse', 'Twenty six second sparse low pulse and soft felt piano single notes, very quiet, contemplative documentary underscore, no drums, no vocals.'],
  ['resolve', 'Twenty six second delicate felt piano notes over a soft low sustained tone, restrained gentle resolution, no drums, no vocals.'],
];
const inputs = [];
for (const [name, text] of beds) {
  const file = `.cache/music/${name}.mp3`;
  if (!existsSync(file)) {
    let part;
    try {
      part = await fetch('https://api.elevenlabs.io/v1/sound-generation?output_format=mp3_44100_128', {
        method: 'POST', headers: {'xi-api-key': key, 'Content-Type': 'application/json', Accept: 'audio/mpeg'},
        body: JSON.stringify({text, duration_seconds: 26, prompt_influence: 0.5}),
      });
    } catch (error) { record('music', `skipped: sound generation network ${error.cause?.code ?? error.name}`); console.log('Music fallback skipped: network unavailable'); process.exit(0); }
    if ([401, 402, 429].includes(part.status)) { record('music', `skipped: Music API HTTP 402, sound generation HTTP ${part.status}`); console.log(`Music fallback skipped: HTTP ${part.status}`); process.exit(0); }
    if (!part.ok) throw new Error(`Music bed ${name}: HTTP ${part.status}`);
    writeFileSync(file, Buffer.from(await part.arrayBuffer()));
    console.log(`Music bed ${name}: written`);
  }
  inputs.push(file);
}
const seconds = musicLengthMs / 1000;
const finalBedDuration = Math.max(26, seconds - 48);
const fadeOut = Math.max(0, seconds - 2);
const filter = `[0:a]atrim=0:26,asetpts=PTS-STARTPTS[a];[1:a]atrim=0:26,asetpts=PTS-STARTPTS[b];[2:a]atrim=0:${finalBedDuration},asetpts=PTS-STARTPTS[c];[a][b]acrossfade=d=2[ab];[ab][c]acrossfade=d=2,atrim=0:${seconds},afade=t=in:st=0:d=1.5,afade=t=out:st=${fadeOut}:d=2,volume=0.55[out]`;
const result = spawnSync('ffmpeg', ['-y', '-loglevel', 'error', '-i', inputs[0], '-i', inputs[1], '-stream_loop', '-1', '-i', inputs[2], '-filter_complex', filter, '-map', '[out]', '-ar', '44100', '-ac', '2', '-b:a', '192k', output], {stdio: 'inherit'});
if (result.status !== 0) throw new Error('Music bed assembly failed');
writeFileSync('.cache/music.json', JSON.stringify({source: 'sound-generation-stitched', seconds, musicApiStatus: 402}, null, 2) + '\n');
record('music', 'written: sound-generation fallback (Music API HTTP 402)');
console.log('Music fallback written');
