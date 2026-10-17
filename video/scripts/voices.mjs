import {readFileSync, writeFileSync} from 'node:fs';
import {key, voiceId, envPath} from './env.mjs';
const path = 'script.json';
const script = JSON.parse(readFileSync(path, 'utf8'));
let chosen = voiceId;
if (key) {
  try {
    const response = await fetch('https://api.elevenlabs.io/v1/voices', {headers: {'xi-api-key': key}});
    if ([401, 429].includes(response.status)) {
      console.log(`Voices: HTTP ${response.status}; skipped`);
    } else if (!response.ok) {
      console.log(`Voices: HTTP ${response.status}; using configured voice if available`);
    } else {
      const premade = (await response.json()).voices?.filter((voice) => voice.category === 'premade') ?? [];
      console.log(`Voices: ${premade.length} premade available`);
      if (!chosen) chosen = premade.find((voice) => voice.voice_id === 'pFZP5JQG7iQjIQuC4Bku')?.voice_id ?? premade[0]?.voice_id ?? '';
    }
  } catch (error) { console.log(`Voices: lookup unavailable (${error.cause?.code ?? error.name}); using configured voice if available`); }
}
if (chosen) {
  script.voices.narrator.id = chosen;
  writeFileSync(path, JSON.stringify(script, null, 2) + '\n');
  if (!voiceId) {
    const previous = readFileSync(envPath, 'utf8');
    const next = /^ELEVENLABS_VOICE_ID=/m.test(previous) ? previous.replace(/^ELEVENLABS_VOICE_ID=.*$/m, `ELEVENLABS_VOICE_ID=${chosen}`) : `${previous.trimEnd()}\nELEVENLABS_VOICE_ID=${chosen}\n`;
    writeFileSync(envPath, next, {mode: 0o600});
  }
  console.log('Voices: narrator configured');
} else console.log('Voices: no narrator voice available');
