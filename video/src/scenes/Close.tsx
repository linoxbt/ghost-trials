import type {SceneProps} from '../timing';
import {Frame} from '../ui/kit';
import {Words} from '../ui/Words';
import {Brand} from '../ui/Brand';
import {SiteVisual} from '../ui/SiteVisual';
export const Close: React.FC<SceneProps> = ({scene, frame}) => <Frame style={{display: 'flex', alignItems: 'center', gap: 75}}><div style={{width: 830}}><div style={{marginBottom: 70}}><Brand width={520} /></div><Words scene={scene} frame={frame} accent="certification" maxWidth={830} /></div><SiteVisual kind="cta" frame={frame} from={scene.from} style={{width: 780, height: 450}} /></Frame>;
