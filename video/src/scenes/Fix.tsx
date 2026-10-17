import type {SceneProps} from '../timing';
import {Words, fontFamilies} from '../ui/Words';
import {Wall} from '../ui/Wall';
import {SiteVisual} from '../ui/SiteVisual';
import {theme} from '../theme';
import {fade, wordTrigger} from '../ui/motion';
export const Fix: React.FC<SceneProps> = ({scene, frame}) => {
  const start = wordTrigger('fix', 'saved') ?? scene.from;
  const locked = fade(frame, start, start + 8);
  return <><Wall frame={frame} mode="fix" />
    <div style={{position: 'absolute', left: 72, top: 180}}><Words scene={scene} frame={frame} accent="saved" maxWidth={1480} /></div>
    <SiteVisual kind="cta" frame={frame} from={scene.from} style={{position: 'absolute', left: 72, top: 470, width: 1050, height: 360}} />
    <div style={{position: 'absolute', right: 72, top: 550, border: `3px solid ${theme.accent}`, borderRadius: 12, padding: '28px 35px', color: theme.accent, fontFamily: fontFamilies.geist, fontWeight: 700, fontSize: 25, letterSpacing: '0.1em', transform: `rotate(-7deg) scale(${0.8 + locked * 0.2})`, opacity: locked}}>ARTIFACT CHECK<br />METRIC CHECK<br />SAVE RULE</div>
  </>;
};
