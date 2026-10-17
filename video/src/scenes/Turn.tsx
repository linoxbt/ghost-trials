import type {SceneProps} from '../timing';
import {Words} from '../ui/Words';
import {AppVisual} from '../ui/AppVisual';
export const Turn: React.FC<SceneProps> = ({scene, frame}) => <>
  <div style={{position: 'absolute', left: 72, top: 170}}><Words scene={scene} frame={frame} accent="scenario" maxWidth={1500} /></div>
  <AppVisual view="turn" scene={scene} frame={frame} style={{position: 'absolute', left: 72, right: 72, top: 430, height: 450}} />
</>;
