import type {SceneProps} from '../timing';
import {Words} from '../ui/Words';
import {SiteVisual} from '../ui/SiteVisual';
export const Turn: React.FC<SceneProps> = ({scene, frame}) => <>
  <div style={{position: 'absolute', left: 72, top: 170}}><Words scene={scene} frame={frame} accent="scenario" maxWidth={1500} /></div>
  <SiteVisual kind="pipeline" frame={frame} from={scene.from} style={{position: 'absolute', left: 72, right: 72, top: 430, height: 425}} />
</>;
