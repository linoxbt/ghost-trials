import type {SceneProps} from '../timing';
import {Frame} from '../ui/kit';
import {Words} from '../ui/Words';
import {Brand} from '../ui/Brand';
import {AppVisual} from '../ui/AppVisual';
export const Open: React.FC<SceneProps> = ({scene, frame}) => <Frame style={{display: 'flex', alignItems: 'center', gap: 60}}>
  <div style={{width: 850, flexShrink: 0}}><div style={{marginBottom: 58}}><Brand width={340} /></div><Words scene={scene} frame={frame} accent="failure" maxWidth={850} /></div>
  <AppVisual view="open" scene={scene} frame={frame} compact style={{width: 780, height: 620, flexShrink: 0}} />
</Frame>;
