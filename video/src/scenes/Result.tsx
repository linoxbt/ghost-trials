import data from '../data.json';
import type {SceneProps} from '../timing';
import {Frame} from '../ui/kit';
import {Words, fontFamilies} from '../ui/Words';
import {Count} from '../ui/Count';
import {theme} from '../theme';
import {fade} from '../ui/motion';
export const Result: React.FC<SceneProps> = ({scene, frame}) => <Frame style={{display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: 54}}><Words scene={scene} frame={frame} accent="zero" /><div style={{display: 'flex', gap: 24, fontFamily: fontFamilies.geist}}>{(Object.keys(data.weights) as Array<keyof typeof data.weights>).map((weight, index) => <div key={weight} style={{width: 395, height: 280, padding: 28, border: '1px solid rgba(25,27,30,0.16)', borderRadius: 18, background: 'rgba(255,255,255,0.3)', transform: `translateY(${(1 - fade(frame, scene.from + index * 6, scene.from + index * 6 + 18)) * 70}px)`, opacity: fade(frame, scene.from + index * 6, scene.from + index * 6 + 18)}}><div style={{height: 8, width: '100%', background: 'rgba(25,27,30,0.1)', borderRadius: 99, marginBottom: 36}}><div style={{height: '100%', width: `${data.weights[weight].value * 100}%`, background: theme.accent, borderRadius: 99, transform: `scaleX(${fade(frame, scene.from + index * 6, scene.from + index * 6 + 22)})`, transformOrigin: 'left'}} /></div><div style={{fontSize: 19, opacity: theme.mutedOpacity, marginBottom: 10, textTransform: 'uppercase', letterSpacing: 2}}>{weight}</div><div style={{fontSize: 64}}><Count weight={weight} frame={frame} from={scene.from + index * 6} /></div></div>)}</div></Frame>;
