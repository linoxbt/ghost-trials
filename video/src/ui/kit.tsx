import type {CSSProperties, ReactNode} from 'react';
export const FRAME_PADDING = 72;
export const Frame: React.FC<{children: ReactNode; style?: CSSProperties}> = ({children, style}) => <div style={{position: 'absolute', inset: FRAME_PADDING, ...style}}>{children}</div>;
