import timing from './timing.json';
export default timing;
export const fps = timing.fps;
export const totalFrames = timing.totalFrames;
export type SceneTiming = (typeof timing.scenes)[number];
export type LineTiming = SceneTiming['lines'][number];
export const scene = (id: string): SceneTiming | undefined => timing.scenes.find((item) => item.id === id);
export const lineAt = (frame: number, sceneId?: string): LineTiming | undefined => {
  const found = sceneId ? scene(sceneId) : timing.scenes.find((item) => item.from <= frame && frame < item.from + item.durationInFrames);
  if (!found) return undefined;
  return found.lines.find((line) => line.startFrame <= frame && frame < line.startFrame + line.durationFrames)
    ?? found.lines.filter((line) => line.startFrame <= frame).at(-1)
    ?? found.lines[0];
};
export const wordAt = (frame: number) => timing.scenes.flatMap((item) => item.lines).flatMap((line) => line.words).find((word) => word.start <= frame && frame < word.end);
export type SceneProps = {scene: SceneTiming; frame: number};
