import type {ComponentType} from 'react';
import {AbsoluteFill, Audio, Sequence, staticFile, useCurrentFrame} from 'remotion';
import timing from './timing';
import type {SceneProps, SceneTiming} from './timing';
import assets from './assets.json';
import {theme} from './theme';
import {fade, wordTrigger} from './ui/motion';
import {Grain} from './ui/Grain';
import {Chrome} from './ui/Chrome';
import {Captions} from './ui/Captions';
import {Open} from './scenes/Open';
import {Problem} from './scenes/Problem';
import {Turn} from './scenes/Turn';
import {Attack} from './scenes/Attack';
import {Fix} from './scenes/Fix';
import {Prove} from './scenes/Prove';
import {Result} from './scenes/Result';
import {Tools} from './scenes/Tools';
import {Different} from './scenes/Different';
import {Close} from './scenes/Close';

export const OVERLAP = 10;
const components: Record<string, ComponentType<SceneProps>> = {open: Open, problem: Problem, turn: Turn, attack: Attack, fix: Fix, prove: Prove, result: Result, tools: Tools, different: Different, close: Close};
const effects: Array<{name: keyof typeof assets.sfx; scene: string; word?: string; volume?: number}> = [
  {name: 'tick', scene: 'open', word: 'failure'},
  {name: 'thud', scene: 'problem', word: 'proof'},
  {name: 'glitch', scene: 'problem', word: 'simulation'},
  {name: 'click', scene: 'turn', word: 'scenario'},
  {name: 'wobble', scene: 'attack', word: 'friction'},
  {name: 'slot', scene: 'fix', word: 'saved'},
  {name: 'riser', scene: 'prove', volume: 0.3},
  {name: 'chime', scene: 'prove', word: 'nine'},
  {name: 'stamp', scene: 'prove', word: 'passed'},
  {name: 'pop', scene: 'result', word: 'one'},
  {name: 'impact', scene: 'result', word: 'zero', volume: 0.35},
  {name: 'typing', scene: 'tools', volume: 0.2},
  {name: 'alarm', scene: 'tools', word: 'GPU'},
];
const ease = (value: number) => value * value * (3 - 2 * value);
const visible = (scene: SceneTiming, index: number, frame: number) => {
  const start = index === 0 ? 0 : scene.from - OVERLAP;
  const end = timing.scenes[index + 1]?.from ?? timing.totalFrames;
  return start <= frame && frame < end;
};

export const Film: React.FC = () => {
  const frame = useCurrentFrame();
  const visibleScenes = timing.scenes.map((scene, index) => ({scene, index})).filter(({scene, index}) => visible(scene, index, frame));
  const current = visibleScenes.at(-1)?.scene ?? timing.scenes[0];
  const speaking = timing.scenes.some((scene) => scene.lines.some((line) => line.startFrame <= frame && frame < line.startFrame + line.durationFrames));
  const musicVolume = (speaking ? 0.06 : 0.16) * fade(frame, 0, 20) * (1 - fade(frame, timing.totalFrames - 50, timing.totalFrames));
  return <AbsoluteFill style={{background: theme.paper}}>
    {visibleScenes.map(({scene, index}) => {
      const Component = components[scene.id];
      const start = index === 0 ? 0 : scene.from - OVERLAP;
      const progress = index === 0 ? 1 : ease(fade(frame, start, start + OVERLAP));
      const frozenFrame = Math.max(frame, scene.from);
      return <AbsoluteFill key={scene.id} style={{opacity: progress, clipPath: index === 0 ? undefined : `inset(0 ${(1 - progress) * 100}% 0 0)`, transform: `scale(${1.03 - progress * 0.03})`, filter: `blur(${(1 - progress) * 10}px)`}}><Component scene={scene} frame={frozenFrame} /></AbsoluteFill>;
    })}
    <Grain />
    <Chrome scene={current} frame={frame} />
    <Captions scene={current} frame={frame} />
    {timing.scenes.flatMap((scene) => scene.lines.map((line) => assets.voice[line.file as keyof typeof assets.voice] && <Sequence key={line.file} from={line.startFrame} durationInFrames={line.durationFrames}><Audio src={staticFile(line.file)} /></Sequence>))}
    {assets.music && <Audio src={staticFile('audio/music.mp3')} volume={musicVolume} />}
    {timing.scenes.slice(1).map((scene) => assets.sfx.whoosh && <Sequence key={`whoosh-${scene.id}`} from={scene.from - OVERLAP} durationInFrames={Math.min(45, timing.totalFrames - scene.from + OVERLAP)}><Audio src={staticFile('audio/sfx/whoosh.mp3')} volume={0.25} /></Sequence>)}
    {effects.map((effect) => {
      if (!assets.sfx[effect.name]) return null;
      const trigger = effect.word ? wordTrigger(effect.scene, effect.word) : timing.scenes.find((scene) => scene.id === effect.scene)?.from;
      if (trigger === undefined) return null;
      return <Sequence key={effect.name} from={trigger} durationInFrames={Math.min(90, timing.totalFrames - trigger)}><Audio src={staticFile(`audio/sfx/${effect.name}.mp3`)} volume={effect.volume ?? 0.45} /></Sequence>;
    })}
  </AbsoluteFill>;
};
