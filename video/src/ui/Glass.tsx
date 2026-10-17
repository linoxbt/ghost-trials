import type {ReactNode} from 'react';
import {theme} from '../theme';
export const Glass: React.FC<{children: ReactNode; width?: number; height?: number}> = ({children, width = 530, height = 440}) => <div style={{position: 'relative', width, height, border: '1px solid rgba(26,26,26,0.12)', borderRadius: 18, background: theme.paper, overflow: 'hidden'}}>{children}</div>;
