import {existsSync, readFileSync} from 'node:fs';
import {fileURLToPath} from 'node:url';

export const envPath = fileURLToPath(new URL('../.env', import.meta.url));
const values = existsSync(envPath) ? Object.fromEntries(readFileSync(envPath, 'utf8').split(/\r?\n/).filter((line) => line && !line.startsWith('#') && line.includes('=')).map((line) => {
  const at = line.indexOf('=');
  return [line.slice(0, at).trim(), line.slice(at + 1).trim().replace(/^(['"])(.*)\1$/, '$2')];
})) : {};
export const key = values.ELEVENLABS_API_KEY || '';
export const voiceId = values.ELEVENLABS_VOICE_ID || '';
export const model = values.ELEVENLABS_MODEL || 'eleven_multilingual_v2';
export const readEnv = () => values;
