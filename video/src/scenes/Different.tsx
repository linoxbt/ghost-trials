import data from '../data.json';
import type {SceneProps} from '../timing';
import {Frame} from '../ui/kit';
import {Words, fontFamilies} from '../ui/Words';
import {theme} from '../theme';
import {SiteVisual} from '../ui/SiteVisual';
import {fade} from '../ui/motion';
export const Different: React.FC<SceneProps> = ({scene, frame}) => <Frame style={{display: 'flex', alignItems: 'center', gap: 70}}><div style={{width: 760}}><Words scene={scene} frame={frame} accent="null" maxWidth={760} /><div style={{fontFamily: fontFamilies.geist, display: 'flex', gap: 48, alignItems: 'center', color: theme.ink, marginTop: 55, transform: `translateY(${(1 - fade(frame, scene.from, scene.from + 20)) * 70}px)`}}><span style={{fontSize: 125, fontWeight: 500}}>null</span><span style={{fontSize: 70, opacity: 0.28}}>≠</span><span style={{fontSize: 125, opacity: 0.35, textDecoration: 'line-through'}}>{data.weights.catastrophic.value}</span></div></div><SiteVisual kind="cta" frame={frame} from={scene.from} style={{width: 900, height: 420}} /></Frame>;
