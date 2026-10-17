import {interpolate} from 'remotion';
import data from '../data.json';
import type {SceneProps} from '../timing';
import {Words, fontFamilies} from '../ui/Words';
import {Wall} from '../ui/Wall';
import {SiteVisual} from '../ui/SiteVisual';
import {theme} from '../theme';
import {wordTrigger} from '../ui/motion';
export const Prove: React.FC<SceneProps> = ({scene, frame}) => {
  const start = wordTrigger('prove', 'nine') ?? scene.from;
  const shown = Math.round(interpolate(frame, [start, start + 18], [0, data.gridTrials.value], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}));
  return <><Wall frame={frame} mode="prove" />
    <div style={{position: 'absolute', left: 72, top: 165}}><Words scene={scene} frame={frame} accent="nine" maxWidth={1560} /></div>
    <div style={{position: 'absolute', left: 72, top: 570, fontFamily: fontFamilies.geist, fontSize: 160, color: theme.ink, fontVariantNumeric: 'tabular-nums', lineHeight: 1}}>{shown}<span style={{fontSize: 22, opacity: 0.45, marginLeft: 18, letterSpacing: 2}}>GRID TRIALS</span></div>
    <SiteVisual kind="pipeline" frame={frame} from={scene.from} style={{position: 'absolute', right: 72, top: 525, width: 790, height: 300}} />
  </>;
};
