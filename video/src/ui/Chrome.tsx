import timing from '../timing';
import type {SceneTiming} from '../timing';
import {theme} from '../theme';
import {fontFamilies} from './Words';
import {Brand} from './Brand';
export const Chrome: React.FC<{scene: SceneTiming; frame: number}> = ({scene, frame}) => {
  const index = timing.scenes.findIndex((item) => item.id === scene.id) + 1;
  const close = timing.scenes.find((item) => item.id === 'close');
  const footerVisible = !close || frame < close.from + 30;
  return <>
    <div style={{position: 'absolute', top: 48, left: 72, zIndex: 10, display: 'flex', alignItems: 'center', gap: 22}}><Brand width={38} markOnly /><div style={{fontFamily: fontFamilies.geist, fontSize: 22, letterSpacing: '0.16em', opacity: 0.55, color: theme.ink}}>// {String(index).padStart(2, '0')} · {scene.id}</div></div>
    {footerVisible && <div style={{position: 'absolute', bottom: 64, left: 72, right: 72, zIndex: 10, display: 'flex', justifyContent: 'space-between', fontFamily: fontFamilies.geist, fontSize: 16, opacity: theme.footerOpacity, color: theme.ink}}><span>Ghost Trials</span><span>ghost-trials.netlify.app</span></div>}
  </>;
};
