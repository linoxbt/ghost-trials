import {Img, staticFile} from 'remotion';
export const Brand: React.FC<{width?: number; markOnly?: boolean}> = ({width = 280, markOnly = false}) => <Img src={staticFile(markOnly ? 'brand/ghost-mark.svg' : 'brand/ghost-logo.svg')} style={{width, height: 'auto'}} />;
