import type {SceneProps} from '../timing';
import {Words} from '../ui/Words';
import {AppVisual} from '../ui/AppVisual';
export const Different: React.FC<SceneProps> = ({scene, frame}) => <>
  <div style={{position: 'absolute', left: 72, top: 165}}><Words scene={scene} frame={frame} accent="null" maxWidth={1560} /></div>
  <AppVisual view="different" scene={scene} frame={frame} style={{position: 'absolute', left: 72, right: 72, top: 440, height: 440}} />
</>;
