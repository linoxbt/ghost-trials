import {existsSync, mkdirSync, readFileSync, writeFileSync} from 'node:fs';
const path = '.cache/status.json';
export const record = (name, status) => {
  mkdirSync('.cache', {recursive: true});
  const current = existsSync(path) ? JSON.parse(readFileSync(path, 'utf8')) : {};
  current[name] = status;
  writeFileSync(path, JSON.stringify(current, null, 2) + '\n');
};
