import {AbsoluteFill} from 'remotion';
import timing from './timing';
import {theme} from './theme';
import {Open} from './scenes/Open';
import {Grain} from './ui/Grain';
import {Chrome} from './ui/Chrome';
export const Poster: React.FC = () => {
  const scene = timing.scenes[0];
  return <AbsoluteFill style={{background: theme.paper}}><Open scene={scene} frame={scene.from + 30} /><Grain /><Chrome scene={scene} frame={scene.from + 30} /></AbsoluteFill>;
};
