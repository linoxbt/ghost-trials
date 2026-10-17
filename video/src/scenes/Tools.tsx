import type {SceneProps} from '../timing';
import {Frame} from '../ui/kit';
import {Words} from '../ui/Words';
import {Footage} from '../ui/Footage';
import {SiteVisual} from '../ui/SiteVisual';
export const Tools: React.FC<SceneProps> = ({scene, frame}) => <Frame style={{display: 'flex', alignItems: 'center', gap: 50}}><div style={{flex: 1}}><Words scene={scene} frame={frame} accent="CPU" maxWidth={870} /><div style={{marginTop: 48}}><SiteVisual kind="site-cards" frame={frame} from={scene.from} style={{width: 840, height: 235}} /></div></div><Footage scene={scene} frame={frame} /></Frame>;
