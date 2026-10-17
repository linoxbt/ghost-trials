import {Composition, Still} from 'remotion';
import {Film} from './Film';
import {Poster} from './Poster';
import {fps, totalFrames} from './timing';
export const RemotionRoot: React.FC = () => <>
  <Composition id="GhostTrials" component={Film} width={1920} height={1080} fps={fps} durationInFrames={totalFrames} />
  <Still id="Poster" component={Poster} width={1920} height={1080} />
</>;
