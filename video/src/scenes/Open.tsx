import type {SceneProps} from '../timing';
import {Frame} from '../ui/kit';
import {Words} from '../ui/Words';
import {SiteVisual} from '../ui/SiteVisual';
import {Brand} from '../ui/Brand';
export const Open: React.FC<SceneProps> = ({scene, frame}) => <Frame style={{display: 'flex', alignItems: 'center', gap: 60}}>
  <div style={{width: 850, flexShrink: 0}}><div style={{marginBottom: 58}}><Brand width={340} /></div><Words scene={scene} frame={frame} accent="failure" maxWidth={850} /></div>
  <SiteVisual kind="hero-copy" frame={frame} from={scene.from} style={{width: 780, height: 570, flexShrink: 0}} />
</Frame>;
