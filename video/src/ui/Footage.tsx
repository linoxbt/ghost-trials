import {Img, interpolate, staticFile} from 'remotion';
import footage from '../footage.json';
import type {SceneTiming} from '../timing';
import {theme} from '../theme';
import {Glass} from './Glass';
import {fontFamilies} from './Words';
export const Footage: React.FC<{scene: SceneTiming; frame: number}> = ({scene, frame}) => {
  const shift = interpolate(frame, [scene.from, scene.from + scene.durationInFrames], [0, 4], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return <Glass width={610} height={410}>
    {footage.captured ? <Img src={staticFile(footage.paths[1])} style={{width: '100%', height: '100%', objectFit: 'cover', transform: `translateX(${shift}px) scale(1.01)`}} /> :
      <div style={{padding: 40, fontFamily: fontFamilies.geist, color: theme.ink, height: '100%', display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: 32}}>
        {['Hunt', 'CPU MuJoCo tabletop', 'Release the Ghost'].map((row) => <div key={row} style={{borderBottom: '1px solid rgba(26,26,26,0.15)', paddingBottom: 16, fontSize: 29}}>{row}</div>)}
        <div style={{position: 'absolute', top: 18, right: 22, fontSize: 13, letterSpacing: 1.5, opacity: 0.5}}>drawn, not captured</div>
      </div>}
  </Glass>;
};
