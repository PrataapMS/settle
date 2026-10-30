import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
// Minimal RFC 8785 canonicaliser as the TS engine would implement it.
function canonical(v) {
  if (v === null || typeof v === 'boolean') return JSON.stringify(v);
  if (typeof v === 'number') { if (!Number.isFinite(v)) throw new Error('non-finite'); return Object.is(v, -0) ? '0' : JSON.stringify(v); }
  if (typeof v === 'string') return JSON.stringify(v);
  if (Array.isArray(v)) return '[' + v.map(canonical).join(',') + ']';
  const keys = Object.keys(v).sort(); // default sort = UTF-16 code units
  return '{' + keys.map(k => JSON.stringify(k) + ':' + canonical(v[k])).join(',') + '}';
}
const sha = s => createHash('sha256').update(s, 'utf8').digest('hex');
const vec = JSON.parse(readFileSync(process.argv[2], 'utf8'));
let bad = 0;
for (const c of vec.cases) {
  const s = canonical(c.value);
  if (s !== c.canonical || sha(s) !== c.sha256) { bad++; console.log('MISMATCH', c.name, s, c.canonical); }
}
// Recompute every log hash of both fixtures.
for (const dir of ['rent-or-buy', 'rent-or-buy-edits']) {
  const log = JSON.parse(readFileSync(`fixtures/${dir}/expected/log.json`, 'utf8'));
  let prev = 'genesis';
  for (const e of log) {
    const { hash, ...rest } = e;
    if (rest.prev_hash !== prev || sha(canonical(rest)) !== hash) { bad++; console.log('HASH MISMATCH', dir, e.seq); }
    prev = hash;
  }
  console.log(dir, 'entries', log.length, 'chain ok');
}
console.log(bad ? `${bad} problems` : 'All vectors and log hashes match in JavaScript');
process.exit(bad ? 1 : 0);
