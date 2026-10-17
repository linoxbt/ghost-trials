import timing from '../timing';
export const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value));
export const fade = (frame: number, start: number, end: number) => clamp((frame - start) / Math.max(1, end - start), 0, 1);
const clean = (word: string) => word.replace(/[^\p{L}\p{N}]/gu, '').toLowerCase();
export const wordTrigger = (sceneId: string, word: string) => timing.scenes.find((scene) => scene.id === sceneId)?.lines.flatMap((line) => line.words).find((item) => clean(item.word) === clean(word))?.start;
