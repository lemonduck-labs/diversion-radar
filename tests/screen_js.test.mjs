// Runs the page's JavaScript screen (app/src/screen.js) against the shared cases in
// radar/brief/spec/screen_cases.json, as the cases file says: compare ok and the set of
// (code, path) pairs, and for schema problems the code only. Reply cases parse first; review
// cases pass their reviewer notes; note cases run the note checks.
// Usage: node tests/screen_js.test.mjs   (exit code 1 on any difference)
import { createRequire } from 'module';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.join(here, '..');
const require = createRequire(import.meta.url);
const S = require(path.join(root, 'app', 'src', 'screen.js'));
const spec = (f) => JSON.parse(fs.readFileSync(path.join(root, 'radar', 'brief', 'spec', f), 'utf8'));
const R = spec('screen_rules.json'), schema = spec('brief.schema.json'), cases = spec('screen_cases.json');
const C = S.compile(R);
const key = (ps) => ps.map((p) => (p.code === 'schema' ? 'schema' : `${p.code} @ ${p.path}`)).sort();
const same = (a, b) => JSON.stringify([...new Set(a)]) === JSON.stringify([...new Set(b)]);
let bad = 0, n = 0;
function check(name, problems, expected) {
  n++;
  const ok = problems.length === 0;
  if (ok !== expected.ok || !same(key(problems), key(expected.problems))) {
    bad++;
    console.log('DIFF', name, '\n  got     ', JSON.stringify(key(problems)), '\n  expected', JSON.stringify(key(expected.problems)));
  }
}
for (const c of cases.cases) check(c.name, S.screenShared(c.draft, cases.contexts[c.context], C, schema, c.review), c.expected);
for (const c of cases.note_cases || []) check('note: ' + c.name, S.noteProblems(c.text, cases.contexts[c.context], 'note', C), c.expected);
for (const c of cases.reply_cases || []) {
  const parsed = S.parseReply(c.reply);
  const problems = parsed.ok ? S.screenShared(parsed.draft, cases.contexts[c.context], C, schema) : [parsed.problem];
  check('reply: ' + c.name, problems, c.expected);
}
console.log(`${n - bad} of ${n} shared cases match`);
process.exit(bad ? 1 : 0);
