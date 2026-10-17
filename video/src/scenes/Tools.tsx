import type {SceneProps} from '../timing';
import {Words} from '../ui/Words';
import {AppVisual} from '../ui/AppVisual';
export const Tools: React.FC<SceneProps> = ({scene, frame}) => <>
  <div style={{position: 'absolute', left: 72, top: 145}}><Words scene={scene} frame={frame} accent="CPU" maxWidth={1640} /></div>
  <AppVisual view="tools" scene={scene} frame={frame} style={{position: 'absolute', left: 72, right: 72, top: 455, height: 425}} />
</>;
