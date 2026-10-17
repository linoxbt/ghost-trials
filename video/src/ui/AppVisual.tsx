import type {CSSProperties, ReactNode} from 'react';
import {Img, interpolate, staticFile} from 'remotion';
import data from '../data.json';
import type {SceneTiming} from '../timing';
import {theme} from '../theme';
import {fade, wordTrigger} from './motion';
import {fontFamilies} from './Words';
import {PhysicalVisual} from './PhysicalVisual';

type View = 'open' | 'problem' | 'turn' | 'attack' | 'fix' | 'prove' | 'result' | 'tools' | 'different' | 'close';
const surface = '#ffffff';
const line = '#e8e6e2';
const muted = '#7a7c7f';
const sidebar = '#191b1e';
const mono = 'IBM Plex Mono, ui-monospace, SFMono-Regular, monospace';
const panel: CSSProperties = {background: surface, border: `1px solid ${line}`, borderRadius: 12, padding: 23};
const small: CSSProperties = {fontFamily: mono, fontSize: 12, letterSpacing: '0.11em', color: muted};
const ease = (value: number) => value * value * (3 - 2 * value);
const progress = (frame: number, start: number, length = 16) => ease(fade(frame, start, start + length));
const mark = <Img src={staticFile('brand/ghost-mark.svg')} style={{width: 33, height: 37}} />;

const Card: React.FC<{children: ReactNode; style?: CSSProperties}> = ({children, style}) => <div style={{...panel, ...style}}>{children}</div>;
const Heading: React.FC<{eyebrow: string; title: string}> = ({eyebrow, title}) => <div style={{marginBottom: 22}}><div style={{...small, color: theme.accent, marginBottom: 9}}>{eyebrow}</div><div style={{fontSize: 30, fontWeight: 650, letterSpacing: -1.2, lineHeight: 1.06}}>{title}</div></div>;

const ViewContent: React.FC<{view: View; scene: SceneTiming; frame: number}> = ({view, scene, frame}) => {
  const trigger = (word: string) => wordTrigger(view, word) ?? scene.from;
  const second = scene.lines[1]?.startFrame ?? Infinity;
  if (view === 'open') return <><Heading eyebrow="WORKSPACE / GHOST HUNT" title="Release the Ghost" />
    <Card style={{display: 'grid', gap: 17}}>
      {[['CONTROLLER', 'Executable policy'], ['TASK', 'Bounded physical conditions'], ['HUNT', 'Search for a failure']].map(([label, value], index) => <div key={label} style={{display: 'flex', justifyContent: 'space-between', gap: 18, borderBottom: index === 2 ? undefined : `1px solid ${line}`, paddingBottom: 14, opacity: progress(frame, scene.from + index * 8)}}><span style={small}>{label}</span><strong style={{fontSize: 16, fontWeight: 550}}>{value}</strong></div>)}
    </Card><div style={{marginTop: 20, background: theme.accent, color: '#fff', borderRadius: 8, padding: 15, fontWeight: 650, textAlign: 'center', transform: `scale(${0.96 + progress(frame, trigger('failure')) * 0.04})`}}>Release the Ghost ↗</div>
  </>;
  if (view === 'problem') return <><Heading eyebrow="EVIDENCE / PROVENANCE" title={frame < second ? 'Outcome ≠ execution' : 'CPU simulation evidence'} />
    <div style={{display: 'flex', gap: 20, height: 230}}>
      <Card style={{flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'space-between'}}><span style={small}>STORED OUTCOME</span><div style={{fontSize: 50, color: theme.ink}}>recorded</div><span style={{color: muted, fontSize: 16}}>A saved value is a record.</span></Card>
      <Card style={{flex: 1, borderColor: theme.accent, transform: `translateY(${(1 - progress(frame, trigger('proof'), 8)) * -90}px)`, opacity: progress(frame, trigger('proof'), 8), display: 'flex', flexDirection: 'column', justifyContent: 'space-between'}}><span style={{...small, color: theme.accent}}>EXECUTION PROOF</span><div style={{fontSize: 50, color: theme.accent}}>required</div><span style={{color: muted, fontSize: 16}}>Simulation evidence needs its own provenance.</span></Card>
    </div>
  </>;
  if (view === 'turn') return <><Heading eyebrow="HUNT / WORKFLOW" title="From hazard to judged trial" />
    <div style={{display: 'flex', gap: 13, alignItems: 'stretch', height: 235}}>{['Hazard', 'Scenario', 'Simulation', 'Judge'].map((name, index) => {const p = progress(frame, trigger('scenario') + index * 7); return <Card key={name} style={{flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'space-between', borderColor: p > 0 ? theme.accent : line, transform: `translateY(${(1 - p) * 32}px)`, opacity: 0.45 + p * 0.55}}><span style={{...small, color: p > 0 ? theme.accent : muted}}>0{index + 1} / STEP</span><strong style={{fontSize: 27, fontWeight: 550}}>{name}</strong><span style={{width: '100%', height: 4, borderRadius: 99, background: p > 0 ? theme.accent : line}} /></Card>;})}</div>
  </>;
  if (view === 'attack') return <><Heading eyebrow="HUNT / BOUNDED SEARCH" title="Physical conditions" />
    <div style={{display: 'flex', gap: 22}}><Card style={{flex: 1}}>{['Friction', 'Mass', 'Timing'].map((name, index) => {const p = progress(frame, trigger(name.toLowerCase())); return <div key={name} style={{display: 'grid', gridTemplateColumns: '170px 1fr', alignItems: 'center', gap: 20, marginBottom: index === 2 ? 0 : 24, fontSize: 20}}><span>{name}</span><div style={{height: 7, borderRadius: 99, background: '#ebe5e0', position: 'relative'}}><div style={{width: `${28 + p * (19 + index * 8)}%`, height: 7, borderRadius: 99, background: theme.accent}} /><span style={{position: 'absolute', top: -8, left: `${28 + p * (19 + index * 8)}%`, width: 22, height: 22, borderRadius: 99, border: `4px solid ${surface}`, background: theme.accent, boxShadow: '0 1px 8px #0002'}} /></div></div>;})}</Card>
    <Card style={{width: 480, padding: 8}}><PhysicalVisual frame={frame} /></Card></div>
  </>;
  if (view === 'fix') {const p = progress(frame, trigger('saved'), 8); return <><Heading eyebrow="GHOST CASE / SAVE RULE" title="Checks before save" />
    <div style={{display: 'flex', alignItems: 'center', gap: 18, height: 235}}><Card style={{flex: 1, height: 220}}><div style={small}>01 / REQUIRED</div><div style={{fontSize: 31, marginTop: 35}}>Artifact check</div><div style={{height: 5, width: '100%', background: line, marginTop: 30}} /></Card><Card style={{flex: 1, height: 220}}><div style={small}>02 / REQUIRED</div><div style={{fontSize: 31, marginTop: 35}}>Metric check</div><div style={{height: 5, width: '100%', background: line, marginTop: 30}} /></Card><Card style={{width: 330, height: 220, background: sidebar, color: '#fff', transform: `translateX(${(1 - p) * 95}px)`, opacity: 0.3 + p * 0.7, borderColor: sidebar}}><div style={{...small, color: '#ffb48c'}}>03 / CONDITIONAL</div><div style={{fontSize: 31, marginTop: 35}}>Save Ghost Case</div><div style={{height: 5, width: `${p * 100}%`, background: theme.accent, marginTop: 30}} /></Card></div>
  </>;}
  if (view === 'prove') {const p = progress(frame, trigger('nine'), 20); return <><Heading eyebrow="EVALUATION / BOUNDED GRID" title="Trials and replay" />
    <div style={{display: 'flex', gap: 30, height: 260}}><Card style={{flex: 1, display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 12}}>{Array.from({length: data.gridTrials.value}, (_, index) => {const cell = progress(frame, trigger('nine') + index * 2, 6); return <div key={index} style={{borderRadius: 7, border: `1px solid ${cell > 0 ? theme.accent : line}`, background: cell > 0 ? `${theme.accent}16` : '#f4f2ef', display: 'grid', placeItems: 'center', transform: `scale(${0.9 + cell * 0.1})`, opacity: 0.45 + cell * 0.55, fontFamily: mono, color: theme.accent, fontSize: 18}}>{String(index + 1).padStart(2, '0')}</div>;})}</Card><Card style={{width: 365, display: 'flex', flexDirection: 'column', justifyContent: 'center'}}><span style={small}>REPLAY TARGET</span><div style={{fontSize: 31, marginTop: 25, lineHeight: 1.1}}>Another controller</div><span style={{color: muted, fontSize: 15, marginTop: 18}}>Same case · separate evaluation</span><div style={{height: 5, background: theme.accent, width: `${p * 100}%`, marginTop: 26}} /></Card></div>
  </>;}
  if (view === 'result') return <><Heading eyebrow="EVALUATION / WEIGHTS" title="Outcome weighting" />
    <Card style={{display: 'grid', gap: 15}}>{(Object.keys(data.weights) as Array<keyof typeof data.weights>).map((weight) => {const p = progress(frame, trigger(weight)); return <div key={weight} style={{display: 'grid', gridTemplateColumns: '190px 1fr 80px', alignItems: 'center', gap: 25, fontSize: 19, textTransform: 'capitalize', opacity: 0.3 + p * 0.7}}><span>{weight}</span><div style={{height: 9, borderRadius: 99, background: line}}><div style={{height: '100%', width: `${data.weights[weight].value * p * 100}%`, borderRadius: 99, background: theme.accent}} /></div><span style={{fontFamily: mono, fontSize: 20, fontVariantNumeric: 'tabular-nums'}}>{data.weights[weight].value.toFixed(2)}</span></div>;})}</Card>
  </>;
  if (view === 'tools') return <><Heading eyebrow="SYSTEM / EXECUTION PATH" title="CPU MuJoCo tabletop" />
    <div style={{display: 'flex', gap: 18, height: 225}}><Card style={{flex: 1, background: sidebar, color: '#fff'}}><span style={{...small, color: '#ffb48c'}}>DEFAULT PATH</span><div style={{fontSize: 35, marginTop: 27}}>Headless simulation</div><div style={{fontFamily: mono, fontSize: 17, marginTop: 30, color: '#dfd7d0'}}>CPU · MuJoCo · No GPU required</div></Card><Card style={{width: 405, opacity: frame < trigger('GPU') ? 0.4 : 1, borderColor: frame < trigger('GPU') ? line : theme.accent}}><span style={small}>GPU PATH</span><div style={{fontSize: 28, marginTop: 27, lineHeight: 1.1}}>Not demonstrated<br />end to end</div></Card></div>
  </>;
  if (view === 'different') return <><Heading eyebrow="REPORT / EVIDENCE STATE" title="Unavailable ≠ zero" />
    <div style={{display: 'flex', gap: 20, height: 235}}><Card style={{flex: 1}}><span style={small}>SCORE VALUE</span><div style={{fontFamily: mono, fontSize: 70, marginTop: 25, color: theme.accent, transform: `translateY(${(1 - progress(frame, trigger('null'))) * 25}px)`, opacity: progress(frame, trigger('null'))}}>null</div><span style={{fontSize: 15, color: muted}}>Unavailable score</span></Card><Card style={{flex: 1, opacity: frame < second ? 0.45 : 1}}><span style={small}>EVIDENCE HANDLING</span><div style={{fontSize: 35, marginTop: 35}}>Insufficient evidence</div><span style={{fontSize: 16, color: muted}}>Excluded · shown separately</span></Card></div>
  </>;
  return <><Heading eyebrow="GHOST TRIALS / EXPERIMENTAL EVALUATION" title="Find the failure." />
    <Card style={{height: 240, background: sidebar, color: '#fff', display: 'flex', alignItems: 'center', gap: 30}}>{mark}<div><div style={{fontSize: 43, fontWeight: 650}}>ghost trials</div><div style={{fontSize: 19, color: '#c2bbb5', marginTop: 10}}>Not a safety certification service.</div></div></Card>
  </>;
};

export const AppVisual: React.FC<{view: View; scene: SceneTiming; frame: number; style?: CSSProperties; compact?: boolean}> = ({view, scene, frame, style, compact = false}) => {
  const intro = progress(frame, scene.from, 20);
  const drift = interpolate(frame, [scene.from, scene.from + scene.durationInFrames], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const nav = ['Overview', 'Release the Ghost', 'Scenarios', 'Trials', 'Reports'];
  const active = ['open', 'turn', 'attack', 'fix', 'prove'].includes(view) ? 'Release the Ghost' : ['problem', 'different'].includes(view) ? 'Reports' : view === 'result' ? 'Trials' : 'Overview';
  return <div style={{position: 'relative', display: 'flex', overflow: 'hidden', background: '#f7f6f3', border: `1px solid ${line}`, borderRadius: 18, boxShadow: '0 25px 65px #191b1e20', transform: `translate(${(-drift * 8).toFixed(2)}px, ${(1 - intro) * 35}px) scale(${0.985 + intro * 0.015 + drift * 0.012})`, opacity: intro, fontFamily: fontFamilies.geist, color: theme.ink, ...style}}>
    <div style={{width: compact ? 155 : 225, flexShrink: 0, background: sidebar, color: '#f8f6f3', padding: compact ? '18px 12px' : '24px 16px'}}><div style={{display: 'flex', gap: 9, alignItems: 'center', fontSize: compact ? 16 : 20, fontWeight: 650}}>{mark}<span>ghost trials</span></div><div style={{marginTop: 32, padding: '14px 10px', border: '1px solid #34363a', borderRadius: 9, background: '#232529', fontSize: compact ? 10 : 14}}>G1 evaluation lab<div style={{fontSize: 10, color: '#aaa', marginTop: 4}}>Simulation workspace</div></div><div style={{...small, color: '#8b8b8f', margin: '30px 10px 14px'}}>WORKSPACE</div>{nav.map((item) => <div key={item} style={{padding: compact ? '10px 8px' : '12px 13px', marginBottom: 3, borderRadius: 6, fontSize: compact ? 11 : 16, color: item === active ? '#ff9b6e' : '#a9aaac', background: item === active ? '#ed622522' : undefined, whiteSpace: 'nowrap'}}>{item}</div>)}<div style={{position: 'absolute', bottom: 18, left: 20, fontFamily: mono, fontSize: compact ? 8 : 11, color: '#8b8b8f'}}>PHYSICAL AI RED-TEAM</div></div>
    <div style={{flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column'}}><div style={{height: compact ? 54 : 62, flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 25px', background: surface, borderBottom: `1px solid ${line}`, fontSize: compact ? 12 : 15, position: 'relative'}}><span><span style={{color: muted}}>Workspace / </span>{active}</span><span style={{color: theme.accent, fontSize: compact ? 10 : 14}}>↗ Release the Ghost</span><span style={{position: 'absolute', bottom: 0, left: 0, height: 3, width: `${drift * 100}%`, background: theme.accent}} /></div><div style={{flex: 1, overflow: 'hidden', padding: compact ? 20 : '22px 28px'}}><ViewContent view={view} scene={scene} frame={frame} /></div><div style={{height: compact ? 25 : 34, borderTop: `1px solid ${line}`, padding: '7px 25px', display: 'flex', justifyContent: 'space-between', color: muted, fontFamily: mono, fontSize: compact ? 8 : 10}}><span>GHOST TRIALS / EXPERIMENTAL EVALUATION</span><span>INTERFACE VISUALIZATION · NO TRIAL EXECUTED</span></div></div>
  </div>;
};
