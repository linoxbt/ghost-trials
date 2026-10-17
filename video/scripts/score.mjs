import {mkdirSync, readFileSync, renameSync, writeFileSync} from 'node:fs';
import {spawnSync} from 'node:child_process';
import {record} from './status.mjs';

const timing = JSON.parse(readFileSync('src/timing.json', 'utf8'));
const seconds = timing.totalFrames / timing.fps;
const rate = 44100;
const length = Math.ceil(seconds * rate);
const left = new Float32Array(length);
const right = new Float32Array(length);
const beat = 60 / 82;
const bars = Math.ceil(seconds / (beat * 4));
const chords = [
  {notes: [50, 57, 60, 65], melody: [69, 72, 69, 65]},
  {notes: [46, 53, 57, 62], melody: [69, 65, 62, 65]},
  {notes: [41, 48, 52, 57], melody: [64, 69, 72, 69]},
  {notes: [48, 55, 62, 64], melody: [67, 64, 62, 64]},
];
const hz = (midi) => 440 * 2 ** ((midi - 69) / 12);

const note = (start, midi, amplitude, secondsLong, pan = 0, soft = false) => {
  const first = Math.max(0, Math.round(start * rate));
  const count = Math.min(length - first, Math.round(secondsLong * rate));
  const frequency = hz(midi);
  const leftGain = Math.sqrt((1 - pan) / 2);
  const rightGain = Math.sqrt((1 + pan) / 2);
  for (let i = 0; i < count; i++) {
    const t = i / rate;
    const attack = 1 - Math.exp(-t * (soft ? 35 : 520));
    const decay = Math.exp(-t * (soft ? 0.75 : 1.45));
    const release = t > secondsLong - 0.25 ? Math.max(0, (secondsLong - t) / 0.25) : 1;
    const envelope = attack * decay * release;
    const phase = 2 * Math.PI * frequency * t;
    const tone = Math.sin(phase) + 0.28 * Math.sin(phase * 2.006) * Math.exp(-t * 1.5)
      + 0.12 * Math.sin(phase * 3.012) * Math.exp(-t * 3.2);
    const hammer = soft ? 0 : 0.018 * Math.sin(phase * 6.2) * Math.exp(-t * 65);
    const value = amplitude * envelope * (tone + hammer);
    left[first + i] += value * leftGain;
    right[first + i] += value * rightGain;
  }
};

for (let bar = 0; bar < bars; bar++) {
  const chord = chords[bar % chords.length];
  const start = bar * beat * 4;
  if (start >= seconds - 2) break;
  note(start, chord.notes[0], 0.115, 2.25, -0.16);
  note(start + beat * 2, chord.notes[1], 0.07, 1.55, -0.12);
  chord.notes.slice(1).forEach((midi) => note(start, midi, 0.021, beat * 3.8, 0.05, true));
  [0, 1, 2, 3].forEach((step) => note(start + step * beat, chord.notes[[1, 2, 3, 2][step]] + 12, 0.06, 0.82, step % 2 ? 0.28 : -0.28));
  [0, 1.5, 2.5, 3.25].forEach((step, index) => note(start + step * beat, chord.melody[index], 0.105, 1.28, index % 2 ? 0.2 : -0.1));
  for (const step of [0, 2]) {
    const pulseStart = Math.round((start + step * beat) * rate);
    for (let i = 0; i < rate * 0.3 && pulseStart + i < length; i++) {
      const t = i / rate;
      const value = 0.019 * Math.sin(2 * Math.PI * 58 * t) * Math.exp(-t * 13);
      left[pulseStart + i] += value;
      right[pulseStart + i] += value;
    }
  }
}

const delayA = Math.round(rate * 0.19);
const delayB = Math.round(rate * 0.31);
for (let i = delayB; i < length; i++) {
  const a = left[i - delayA];
  const b = right[i - delayB];
  left[i] += a * 0.14 + b * 0.07;
  right[i] += b * 0.14 + a * 0.07;
}
let peak = 0;
for (let i = 0; i < length; i++) {
  const time = i / rate;
  const fadeIn = Math.min(1, time / 1.4);
  const fadeOut = Math.min(1, Math.max(0, (seconds - time) / 3));
  left[i] *= fadeIn * fadeOut;
  right[i] *= fadeIn * fadeOut;
  peak = Math.max(peak, Math.abs(left[i]), Math.abs(right[i]));
}
const gain = 0.75 / Math.max(peak, 0.001);
const samples = new Int16Array(length * 2);
for (let i = 0; i < length; i++) {
  samples[2 * i] = Math.round(Math.max(-1, Math.min(1, left[i] * gain)) * 32767);
  samples[2 * i + 1] = Math.round(Math.max(-1, Math.min(1, right[i] * gain)) * 32767);
}
mkdirSync('.cache/score', {recursive: true});
mkdirSync('public/audio', {recursive: true});
const raw = '.cache/score/music.s16le';
const mastered = '.cache/score/music.mp3';
writeFileSync(raw, Buffer.from(samples.buffer));
const result = spawnSync('ffmpeg', ['-y', '-hide_banner', '-loglevel', 'error', '-f', 's16le', '-ar', String(rate), '-ac', '2', '-i', raw, '-af', 'loudnorm=I=-18:TP=-3:LRA=9', '-c:a', 'libmp3lame', '-b:a', '192k', mastered], {stdio: 'inherit'});
if (result.status !== 0) throw new Error('Score encoding failed');
renameSync(mastered, 'public/audio/music.mp3');
writeFileSync('.cache/score.json', JSON.stringify({source: 'original generated piano score', bpm: 82, seconds}, null, 2) + '\n');
record('music', 'written: original piano score');
console.log(`Original piano score written: ${seconds.toFixed(2)} seconds`);
