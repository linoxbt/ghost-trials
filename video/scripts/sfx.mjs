import {existsSync, mkdirSync, writeFileSync} from 'node:fs';
import {key} from './env.mjs';
import {record} from './status.mjs';
const effects = [
  ['tick', 'Single crisp clock tick, close, dry, short.', 0.5],
  ['alarm', 'Short low digital alarm pulse, two tones, tense, clean, no music.', 1.2],
  ['glitch', 'Short digital glitch burst, crisp static, single.', 0.6],
  ['thud', 'A heavy case dropping out of a wall, deep thud, a little debris, close.', 1.0],
  ['slot', 'A case sliding into a wall and locking with one solid clunk.', 0.9],
  ['wobble', 'A case rattling loose, then dropping with a dull thud.', 1.4],
  ['whoosh', 'Soft fast airy whoosh, one transition, no music.', 0.8],
  ['riser', 'Short airy riser, no drums, rising to one peak.', 2.5],
  ['impact', 'Deep clean impact, warm sub tail, one hit.', 2.0],
  ['click', 'Soft modern UI click, single, short.', 0.5],
  ['pop', 'Soft UI pop, single, short.', 0.5],
  ['stamp', 'Firm rubber stamp on paper, one hit, dry.', 0.6],
  ['chime', 'Two soft ascending notes, clean, short tail.', 1.5],
  ['cash', 'Two quick soft digital blips, clean, no melody.', 0.7],
  ['typing', 'Fast soft keyboard typing, close, dry, two seconds.', 2.0],
];
if (!key) { record('sfx', 'skipped: missing key'); console.log('SFX skipped: missing key'); process.exit(0); }
mkdirSync('public/audio/sfx', {recursive: true});
let written = 0, cached = 0;
for (const [name, text, duration_seconds] of effects) {
  const path = `public/audio/sfx/${name}.mp3`;
  if (existsSync(path)) { cached++; continue; }
  let response;
  try {
    response = await fetch('https://api.elevenlabs.io/v1/sound-generation?output_format=mp3_44100_128', {
      method: 'POST', headers: {'xi-api-key': key, 'Content-Type': 'application/json', Accept: 'audio/mpeg'},
      body: JSON.stringify({text, duration_seconds, prompt_influence: 0.5}),
    });
  } catch (error) { record('sfx', `skipped: ${error.cause?.code ?? error.name}`); console.log('SFX skipped: network unavailable'); process.exit(0); }
  if ([401, 402, 429].includes(response.status)) { record('sfx', `skipped: HTTP ${response.status}; ${written} written`); console.log(`SFX skipped: HTTP ${response.status}`); process.exit(0); }
  if (!response.ok) throw new Error(`SFX ${name}: HTTP ${response.status}`);
  writeFileSync(path, Buffer.from(await response.arrayBuffer()));
  written++;
  console.log(`SFX ${name}: written`);
}
record('sfx', `written: ${written} new, ${cached} cached`);
