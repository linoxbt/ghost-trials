import {mkdirSync, readFileSync, writeFileSync} from 'node:fs';
import {key, voiceId, model} from './env.mjs';
if (!key) { console.log('Audition skipped: missing key'); process.exit(0); }
const script = JSON.parse(readFileSync('script.json', 'utf8'));
const id = voiceId || script.voices.narrator.id;
if (!id) { console.log('Audition skipped: missing voice'); process.exit(0); }
mkdirSync('.cache/audition', {recursive: true});
for (let take = 1; take <= 2; take++) {
  const response = await fetch(`https://api.elevenlabs.io/v1/text-to-speech/${encodeURIComponent(id)}?output_format=mp3_44100_128`, {
    method: 'POST', headers: {'xi-api-key': key, 'Content-Type': 'application/json', Accept: 'audio/mpeg'},
    body: JSON.stringify({text: script.scenes[0].lines[0].text, model_id: model, voice_settings: script.voices.narrator.settings}),
  });
  if ([401, 429].includes(response.status)) { console.log(`Audition skipped: HTTP ${response.status}`); process.exit(0); }
  if (!response.ok) { console.log(`Audition skipped: HTTP ${response.status}`); process.exit(0); }
  writeFileSync(`.cache/audition/take-${take}.mp3`, Buffer.from(await response.arrayBuffer()));
  console.log(`Audition take ${take}: written`);
}
