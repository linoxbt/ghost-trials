import {createHash} from 'node:crypto';
import {existsSync, mkdirSync, readFileSync, writeFileSync} from 'node:fs';
import {key, voiceId, model} from './env.mjs';
import {record} from './status.mjs';

const script = JSON.parse(readFileSync('script.json', 'utf8'));
const id = voiceId || script.voices.narrator.id;
mkdirSync('public/audio/vo', {recursive: true});
mkdirSync('.cache/words', {recursive: true});
mkdirSync('.cache/vo', {recursive: true});
mkdirSync('public/alignment', {recursive: true});
if (!key || !id) {
  writeFileSync('public/audio/vo/MISSING.txt', 'Voice generation skipped: missing key or voice ID.\n');
  record('voice', 'skipped: missing key or voice ID');
  console.log('Voice skipped: missing key or voice ID');
  process.exit(0);
}
const alignedWords = (alignment) => {
  const chars = alignment?.characters ?? [];
  const starts = alignment?.character_start_times_seconds ?? [];
  const ends = alignment?.character_end_times_seconds ?? [];
  const words = [];
  let word = '', start = 0, end = 0;
  const flush = () => { if (word) words.push({word, start, end}); word = ''; };
  chars.forEach((char, i) => {
    if (/\s/.test(char)) { flush(); return; }
    if (!word) start = starts[i] ?? 0;
    word += char;
    end = ends[i] ?? start;
  });
  flush();
  return words;
};
let written = 0, cached = 0;
for (const scene of script.scenes) for (let index = 0; index < scene.lines.length; index++) {
  const line = scene.lines[index];
  const stem = `${scene.id}_${index}`;
  const mp3 = `public/audio/vo/${stem}.mp3`;
  const wordFile = `.cache/words/${stem}.json`;
  const shaFile = `.cache/vo/${stem}.sha`;
  const packagedWords = `public/alignment/${stem}.json`;
  const packagedSha = `public/alignment/${stem}.sha`;
  const settings = script.voices[line.voice].settings;
  const hash = createHash('sha1').update(JSON.stringify([line.text, id, settings, model])).digest('hex');
  if (existsSync(mp3) && existsSync(wordFile) && existsSync(shaFile) && readFileSync(shaFile, 'utf8').trim() === hash) { cached++; continue; }
  if (existsSync(mp3) && existsSync(packagedWords) && existsSync(packagedSha) && readFileSync(packagedSha, 'utf8').trim() === hash) {
    writeFileSync(wordFile, readFileSync(packagedWords));
    writeFileSync(shaFile, hash + '\n');
    cached++;
    continue;
  }
  let response;
  try {
    response = await fetch(`https://api.elevenlabs.io/v1/text-to-speech/${encodeURIComponent(id)}/with-timestamps?output_format=mp3_44100_128`, {
      method: 'POST', headers: {'xi-api-key': key, 'Content-Type': 'application/json', Accept: 'application/json'},
      body: JSON.stringify({text: line.text, model_id: model, voice_settings: settings}),
    });
  } catch (error) { record('voice', `skipped: ${error.cause?.code ?? error.name}`); console.log('Voice skipped: network unavailable'); process.exit(0); }
  if ([401, 402, 429].includes(response.status)) { record('voice', `skipped: HTTP ${response.status}`); console.log(`Voice skipped: HTTP ${response.status}`); process.exit(0); }
  if (!response.ok) throw new Error(`Voice ${stem}: HTTP ${response.status}`);
  const body = await response.json();
  const words = alignedWords(body.alignment);
  if (!body.audio_base64 || !words.length) throw new Error(`Voice ${stem}: missing audio or alignment`);
  writeFileSync(mp3, Buffer.from(body.audio_base64, 'base64'));
  writeFileSync(wordFile, JSON.stringify({words}, null, 2) + '\n');
  writeFileSync(shaFile, hash + '\n');
  writeFileSync(packagedWords, JSON.stringify({words}, null, 2) + '\n');
  writeFileSync(packagedSha, hash + '\n');
  written++;
  console.log(`Voice ${stem}: written`);
}
record('voice', written ? `written: ${written} lines` : cached ? `written: ${cached} cached lines` : 'skipped: no lines');
console.log(`Voice: ${written} written, ${cached} cached`);
