import {interpolate} from 'remotion';
import data from '../data.json';
import {wordTrigger} from './motion';

export const PhysicalVisual: React.FC<{frame: number}> = ({frame}) => {
  const amount = ['friction', 'mass', 'timing'].reduce((sum, word) => {
    const start = wordTrigger('attack', word) ?? 0;
    return sum + interpolate(frame, [start, start + 12], [0, 17], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  }, 0);
  return <div style={{height: '100%', borderRadius: 10, background: '#202326', overflow: 'hidden', position: 'relative'}}>
    <svg viewBox="0 0 500 220" width="100%" height="100%" aria-label="Illustrative block and tabletop parameter diagram">
      <defs><linearGradient id="table" x1="0" y1="0" x2="1" y2="1"><stop stopColor="#454949"/><stop offset="1" stopColor="#292d2e"/></linearGradient></defs>
      <polygon points="25,163 192,79 475,123 306,208" fill="url(#table)" stroke="#717370" strokeWidth="1" />
      {[0, 1, 2, 3, 4, 5].map((index) => <path key={`a${index}`} d={`M${25 + index * 34},${163 - index * 17} L${306 + index * 34},${208 - index * 17}`} stroke="#6f7471" strokeOpacity=".35" />)}
      {[0, 1, 2, 3, 4].map((index) => <path key={`b${index}`} d={`M${25 + index * 70},${163 + index * 11} L${192 + index * 70},${79 + index * 11}`} stroke="#6f7471" strokeOpacity=".35" />)}
      <path d="M238 112 C284 106 326 105 382 113" fill="none" stroke="#f36b2b" strokeWidth="2" strokeDasharray="5 5" />
      <path d="m376 107 9 6-10 5" fill="none" stroke="#f36b2b" strokeWidth="2" />
      <ellipse cx={186 + amount} cy="170" rx="48" ry="14" fill="#000" opacity=".24" />
      <g transform={`translate(${amount},0)`}>
        <polygon points="146,108 188,88 232,107 190,128" fill="#ffad76" />
        <polygon points="146,108 190,128 190,180 146,160" fill="#ed6225" />
        <polygon points="190,128 232,107 232,158 190,180" fill="#ad471c" />
      </g>
      <circle cx="399" cy="115" r="21" fill="none" stroke="#f36b2b" strokeWidth="2" strokeDasharray="4 4" opacity=".8" />
      <text x="22" y="28" fill="#ffba8e" fontFamily="monospace" fontSize="11" letterSpacing="2">CONCEPTUAL PARAMETER VIEW</text>
      <text x="22" y="49" fill="#b4b9b5" fontFamily="monospace" fontSize="10">ILLUSTRATION · NOT A TRIAL RECORDING</text>
      <text x="346" y="30" fill="#ddd5ce" fontFamily="monospace" fontSize="12">{data.budgetMin.value}–{data.budgetMax.value} TRIAL BUDGET</text>
    </svg>
  </div>;
};
