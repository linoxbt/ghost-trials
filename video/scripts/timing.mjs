import {existsSync, readFileSync, writeFileSync} from 'node:fs';
const FPS = 30;
const script = JSON.parse(readFileSync('script.json', 'utf8'));
let cursor = 8;
const scenes = script.scenes.map((scene, sceneIndex) => {
  const from = cursor;
  const lines = scene.lines.map((line, index) => {
    const stem = `${scene.id}_${index}`;
    const wordFile = existsSync(`.cache/words/${stem}.json`) ? `.cache/words/${stem}.json` : `public/alignment/${stem}.json`;
    const cached = existsSync(wordFile) ? JSON.parse(readFileSync(wordFile, 'utf8')).words : null;
    const tokens = line.text.split(/\s+/);
    const source = cached?.length ? cached : tokens.map((word, i) => ({word, start: i / 2.6, end: (i + 1) / 2.6}));
    const words = source.map((word) => {
      const start = cursor + Math.max(0, Math.round(word.start * FPS));
      return {word: word.word, start, end: Math.max(start + 1, cursor + Math.round(word.end * FPS))};
    });
    const durationFrames = Math.max(1, ...words.map((word) => word.end - cursor));
    const result = {text: line.text, file: `audio/vo/${stem}.mp3`, startFrame: cursor, durationFrames, spoken: Boolean(cached?.length), words};
    cursor += durationFrames + (index < scene.lines.length - 1 ? 8 : 0);
    return result;
  });
  const durationInFrames = cursor - from;
  cursor += sceneIndex < script.scenes.length - 1 ? 12 : 20;
  return {id: scene.id, from, durationInFrames, lines};
});
writeFileSync('src/timing.json', JSON.stringify({fps: FPS, totalFrames: cursor, scenes}, null, 2) + '\n');
writeFileSync('src/assets.json', JSON.stringify({voice: Object.fromEntries(scenes.flatMap((scene) => scene.lines.map((line) => [line.file, existsSync(`public/${line.file}`)]))), music: existsSync('public/audio/music.mp3'), sfx: Object.fromEntries(['tick','alarm','glitch','thud','slot','wobble','whoosh','riser','impact','click','pop','stamp','chime','cash','typing'].map((name) => [name, existsSync(`public/audio/sfx/${name}.mp3`)])), design: Object.fromEntries(['tick','thud','click','slot','chime','pop','whoosh'].map((name) => [name, existsSync(`public/audio/design/${name}.mp3`)]))}, null, 2) + '\n');
console.log(`Timing: ${cursor} frames`);
