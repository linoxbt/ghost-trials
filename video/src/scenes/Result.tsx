import type {SceneProps} from '../timing';
import {Words} from '../ui/Words';
import {AppVisual} from '../ui/AppVisual';
export const Result: React.FC<SceneProps> = ({scene, frame}) => <>
  <div style={{position: 'absolute', left: 72, top: 145}}><Words scene={scene} frame={frame} accent="zero" maxWidth={1690} /></div>
  <AppVisual view="result" scene={scene} frame={frame} style={{position: 'absolute', left: 72, right: 72, top: 455, height: 425}} />
</>;
