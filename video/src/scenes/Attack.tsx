import type {SceneProps} from '../timing';
import {Words, fontFamilies} from '../ui/Words';
import {Wall} from '../ui/Wall';
import {SiteVisual} from '../ui/SiteVisual';
import {theme} from '../theme';
import {fade} from '../ui/motion';
export const Attack: React.FC<SceneProps> = ({scene, frame}) => <>
  <Wall frame={frame} mode="attack" />
  <div style={{position: 'absolute', left: 72, top: 170}}><Words scene={scene} frame={frame} accent="friction" maxWidth={1480} /></div>
  <SiteVisual kind="pipeline" frame={frame} from={scene.from} style={{position: 'absolute', left: 72, top: 535, width: 1080, height: 315}} />
  <div style={{position: 'absolute', right: 72, top: 550, width: 550, display: 'flex', flexDirection: 'column', gap: 15, fontFamily: fontFamilies.geist}}>
    {['FRICTION', 'MASS', 'TIMING'].map((name, index) => <div key={name} style={{height: 82, border: '1px solid rgba(25,27,30,0.15)', borderRadius: 12, display: 'flex', alignItems: 'center', padding: '0 26px', background: theme.paper, transform: `translateX(${(1 - fade(frame, scene.from + index * 7, scene.from + index * 7 + 16)) * 80}px)`, opacity: fade(frame, scene.from + index * 7, scene.from + index * 7 + 16), color: theme.ink, fontSize: 25, letterSpacing: '0.12em'}}><span style={{width: 10, height: 10, borderRadius: 99, background: theme.accent, marginRight: 20}} />{name}</div>)}
  </div>
</>;
