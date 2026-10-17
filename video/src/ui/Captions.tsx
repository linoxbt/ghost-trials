import type {SceneTiming} from '../timing';
import {lineAt} from '../timing';
import {theme} from '../theme';
import {fontFamilies} from './Words';
export const Captions: React.FC<{scene: SceneTiming; frame: number}> = ({scene, frame}) => {
  if (scene.id === 'close' || (scene.id === 'open' && frame < 20)) return null;
  const line = lineAt(frame, scene.id) ?? scene.lines[0];
  return <div style={{position: 'absolute', left: 72, bottom: 130, zIndex: 10, maxWidth: 1700, borderRadius: 999, background: 'rgba(26,26,26,0.07)', padding: '15px 24px', display: 'flex', gap: 6, fontFamily: fontFamilies.geist, fontSize: 17, color: theme.ink}}>
    {line.words.map((word, index) => {
      const active = word.start <= frame && frame < word.end;
      return <span key={index} style={{opacity: active ? 1 : theme.mutedOpacity, fontWeight: active ? 650 : 400}}>{word.word}</span>;
    })}
  </div>;
};
