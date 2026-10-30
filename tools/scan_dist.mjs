import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';
// Fails if the build output contains a key or the name of a server-side secret (docs/10, Keys and secrets).
const patterns = [/sk-or-v1-/, /OPENROUTER_API_KEY/, /JEV_API_KEY/, /TURNSTILE_SECRET_KEY/, /SESSION_SECRET/, /IP_HASH_SECRET/];
const root = process.argv[2] ?? 'dist';
const files = [];
const walk = dir => { for (const f of readdirSync(dir)) { const p = join(dir, f); statSync(p).isDirectory() ? walk(p) : files.push(p); } };
walk(root);
let bad = 0;
for (const p of files) {
  const text = readFileSync(p, 'latin1');
  for (const re of patterns) if (re.test(text)) { bad++; console.log('SECRET PATTERN', re.source, 'in', p); }
}
if (bad) process.exit(1);
console.log(`No secret patterns in ${files.length} files under ${root}`);
