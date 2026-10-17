import {existsSync, readFileSync, writeFileSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
const sourceRoot = existsSync('/tmp/ghost-trials/README.md') ? '/tmp/ghost-trials' : fileURLToPath(new URL('../../', import.meta.url));
const readme = readFileSync(`${sourceRoot}/README.md`, 'utf8');
const hunt = readFileSync(`${sourceRoot}/docs/HUNT.md`, 'utf8');
const checks = [
  ['nine grid trials', /nine bounded grid trials/i, readme],
  ['budget 3 to 50', /3[–-]50/, hunt],
  ['weight 1.00', /\| Avoided \| 1\.00 \|/, readme],
  ['weight 0.65', /\| Mitigated \| 0\.65 \|/, readme],
  ['weight 0.20', /\| Failed \| 0\.20 \|/, readme],
  ['weight 0.00', /\| Catastrophic \| 0\.00 \|/, readme],
  ['null, not zero', /null.{0,5}not zero/i, readme],
  ['not a safety-certification service', /not a safety-certification service/i, readme],
  ['not proof', /not execution proof/i, readme],
  ['simulation evidence', /simulation evidence/i, readme],
];
const missing = checks.filter(([, pattern, text]) => !pattern.test(text)).map(([label]) => label);
if (missing.length) { console.error(`Missing source phrase: ${missing.join(', ')}`); process.exit(1); }
const data = {
  gridTrials: {value: 9, source: 'README.md: CPU smoke check'},
  budgetMin: {value: 3, source: 'docs/HUNT.md: trial budget'},
  budgetMax: {value: 50, source: 'docs/HUNT.md: trial budget'},
  weights: {
    avoided: {value: 1.00, source: 'README.md: Experimental evaluation score'},
    mitigated: {value: 0.65, source: 'README.md: Experimental evaluation score'},
    failed: {value: 0.20, source: 'README.md: Experimental evaluation score'},
    catastrophic: {value: 0.00, source: 'README.md: Experimental evaluation score'},
  },
  nullNotZero: {value: 'null, not zero', source: 'README.md: Experimental evaluation score'},
  certification: {value: 'not a safety-certification service', source: 'README.md: introduction'},
  storedOutcome: {value: 'not execution proof', source: 'README.md: Experimental evaluation score'},
  cpuEvidence: {value: 'simulation evidence', source: 'README.md: Production hardening'},
};
writeFileSync('src/data.json', JSON.stringify(data, null, 2) + '\n');
console.log('Data: verified against README.md and docs/HUNT.md');
