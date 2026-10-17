import {interpolate} from 'remotion';
import data from '../data.json';
import {theme} from '../theme';
type Weight = keyof typeof data.weights;
export const Count: React.FC<{weight: Weight; frame: number; from: number}> = ({weight, frame, from}) => {
  const target = data.weights[weight].value;
  const shown = interpolate(frame, [from, from + 18], [0, target], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return <span style={{fontVariantNumeric: 'tabular-nums', color: theme.ink}}>{shown.toFixed(2)}</span>;
};
