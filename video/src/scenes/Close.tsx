import type {SceneProps} from '../timing';
import {Frame} from '../ui/kit';
import {Words} from '../ui/Words';
import {Brand} from '../ui/Brand';
import {AppVisual} from '../ui/AppVisual';
export const Close: React.FC<SceneProps> = ({scene, frame}) => <Frame style={{display: 'flex', alignItems: 'center', gap: 75}}><div style={{width: 830}}><div style={{marginBottom: 70}}><Brand width={520} /></div><Words scene={scene} frame={frame} accent="certification" maxWidth={830} /></div><AppVisual view="close" scene={scene} frame={frame} compact style={{width: 780, height: 500}} /></Frame>;
