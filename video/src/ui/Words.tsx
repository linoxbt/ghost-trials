import {loadVariableFont as loadGeist} from '@remotion/google-fonts/Geist';
import {loadFont as loadInstrumentSerif} from '@remotion/google-fonts/InstrumentSerif';
import type {SceneTiming} from '../timing';
import {lineAt} from '../timing';
import {theme} from '../theme';
const geist = loadGeist('normal', {subsets: ['latin']}).fontFamily;
const serif = loadInstrumentSerif('italic', {weights: ['400'], subsets: ['latin']}).fontFamily;
const clean = (word: string) => word.replace(/[^\p{L}\p{N}]/gu, '').toLowerCase();
export const fontFamilies = {geist, serif};
export const Words: React.FC<{scene: SceneTiming; frame: number; accent: string; maxWidth?: number}> = ({scene, frame, accent, maxWidth = 1480}) => {
  const line = lineAt(frame, scene.id) ?? scene.lines[0];
  let accented = false;
  return <div style={{position: 'relative', zIndex: 2, fontFamily: geist, fontSize: 78, fontWeight: 500, letterSpacing: -3.2, lineHeight: 1.02, maxWidth, color: theme.ink}}>
    {line.text.split(/(\s+)/).map((part, index) => {
      if (/^\s+$/.test(part)) return part;
      const match = !accented && clean(part) === clean(accent);
      if (match) accented = true;
      return <span key={index} style={match ? {fontFamily: serif, fontStyle: 'italic', color: theme.accent, fontWeight: 400} : undefined}>{part}</span>;
    })}
  </div>;
};
