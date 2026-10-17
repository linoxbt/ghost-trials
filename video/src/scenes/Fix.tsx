import type {SceneProps} from '../timing';
import {Words} from '../ui/Words';
import {AppVisual} from '../ui/AppVisual';
export const Fix: React.FC<SceneProps> = ({scene, frame}) => <>
  <div style={{position: 'absolute', left: 72, top: 180}}><Words scene={scene} frame={frame} accent="saved" maxWidth={1480} /></div>
  <AppVisual view="fix" scene={scene} frame={frame} style={{position: 'absolute', left: 72, right: 72, top: 440, height: 440}} />
</>;
