import type {SceneProps} from '../timing';
import {Words} from '../ui/Words';
import {AppVisual} from '../ui/AppVisual';
export const Problem: React.FC<SceneProps> = ({scene, frame}) => <>
  <div style={{position: 'absolute', left: 72, top: 175}}><Words scene={scene} frame={frame} accent="proof" maxWidth={1430} /></div>
  <AppVisual view="problem" scene={scene} frame={frame} style={{position: 'absolute', left: 72, right: 72, top: 440, height: 440}} />
</>;
