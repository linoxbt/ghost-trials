import {interpolate} from 'remotion';
import data from '../data.json';
import {theme} from '../theme';
import {wordTrigger} from './motion';
type Mode = 'problem' | 'attack' | 'fix' | 'prove';
export const Wall: React.FC<{frame: number; mode: Mode}> = ({frame, mode}) => {
  const failure = wordTrigger('open', 'failure') ?? 0;
  const proof = wordTrigger('problem', 'proof') ?? 0;
  const saved = wordTrigger('fix', 'saved') ?? 0;
  const nine = wordTrigger('prove', 'nine') ?? 0;
  const friction = wordTrigger('attack', 'friction') ?? 0;
  const motion = (trigger: number) => interpolate(frame, [trigger, trigger + 8], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return <div style={{position: 'absolute', right: 95, top: 230, width: 545, height: 385, display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, opacity: mode === 'problem' ? 0.48 : 0.88}}>
    {Array.from({length: data.gridTrials.value}, (_, index) => {
      let drop = index === 1 ? motion(failure) : index === 4 ? motion(proof) : 0;
      if (index === 6 && mode === 'attack') drop = motion(friction);
      if (mode === 'fix' && index === 1) drop *= 1 - motion(saved);
      if (frame >= nine) drop *= 1 - motion(nine);
      return <div key={index} style={{height: 106, borderRadius: 16, border: '2px solid rgba(26,26,26,0.25)', background: 'rgba(26,26,26,0.08)', transform: `translateY(${drop * 126}px)`, opacity: 1 - drop * 0.48}} />;
    })}
    <div style={{position: 'absolute', bottom: -57, right: 0, fontFamily: 'monospace', color: theme.ink, opacity: 0.45, fontSize: 15, letterSpacing: 2}}>BOUNDED TRIALS</div>
  </div>;
};
