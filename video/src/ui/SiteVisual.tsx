import type {CSSProperties} from 'react';
import {Img, interpolate, staticFile} from 'remotion';
import {theme} from '../theme';
import {fontFamilies} from './Words';
import footage from '../footage.json';

type Kind = 'hero-copy' | 'site-cards' | 'pipeline' | 'cta';
const paths: Record<Kind, string> = {
  'hero-copy': 'footage/crops/hero-copy.png',
  'site-cards': 'footage/crops/site-cards.png',
  pipeline: 'footage/crops/pipeline.png',
  cta: 'footage/crops/cta.png',
};

export const SiteVisual: React.FC<{kind: Kind; frame: number; from: number; style?: CSSProperties; label?: string}> = ({kind, frame, from, style, label = 'CAPTURED WEBSITE'}) => {
  if (!footage.captured) return null;
  const rise = interpolate(frame, [from, from + 22], [32, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const reveal = interpolate(frame, [from, from + 20], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const drift = interpolate(frame, [from, from + 180], [-9, 9], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return <div style={{position: 'relative', overflow: 'hidden', borderRadius: 20, border: '1px solid rgba(25,27,30,0.16)', background: theme.paper, boxShadow: '0 28px 70px rgba(25,27,30,0.12)', transform: `translateY(${rise}px)`, opacity: reveal, ...style}}>
    <Img src={staticFile(paths[kind])} style={{width: '100%', height: '100%', objectFit: 'cover', objectPosition: kind === 'cta' || kind === 'hero-copy' ? 'left center' : 'center', transform: kind === 'cta' || kind === 'hero-copy' ? 'scale(1.005)' : `translateX(${drift}px) scale(1.035)`}} />
    <div style={{position: 'absolute', top: 0, left: 0, right: 0, height: 6, background: theme.accent}} />
    <div style={{position: 'absolute', right: 18, bottom: 16, borderRadius: 999, background: theme.ink, color: theme.paper, padding: '9px 14px', fontFamily: fontFamilies.geist, fontSize: 12, fontWeight: 600, letterSpacing: '0.12em'}}>{label}</div>
  </div>;
};
