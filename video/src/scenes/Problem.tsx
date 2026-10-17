import type {SceneProps} from '../timing';
import {Words} from '../ui/Words';
import {Wall} from '../ui/Wall';
import {SiteVisual} from '../ui/SiteVisual';
export const Problem: React.FC<SceneProps> = ({scene, frame}) => <>
  <Wall frame={frame} mode="problem" />
  <div style={{position: 'absolute', left: 72, top: 175}}><Words scene={scene} frame={frame} accent="proof" maxWidth={1430} /></div>
  <SiteVisual kind="site-cards" frame={frame} from={scene.from} style={{position: 'absolute', left: 72, right: 72, top: 490, height: 360}} />
</>;
