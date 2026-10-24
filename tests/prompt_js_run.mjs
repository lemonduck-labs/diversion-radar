// Prints the page's drafting prompt (app/src/screen.js buildPrompt) for the context, notes and
// lessons in a JSON file, so tests/test_app_page.py can compare it with radar/brief/prompt.py.
// Usage: node tests/prompt_js_run.mjs INPUT.json
import { createRequire } from 'module';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
const root = path.join(path.dirname(fileURLToPath(import.meta.url)), '..');
const require = createRequire(import.meta.url);
const S = require(path.join(root, 'app', 'src', 'screen.js'));
const spec = (f) => fs.readFileSync(path.join(root, 'radar', 'brief', 'spec', f), 'utf8');
const input = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const out = S.buildPrompt(spec('prompt.md'), JSON.parse(spec('screen_rules.json')), JSON.parse(spec('brief.schema.json')), input.context, input.review, input.lessons);
process.stdout.write(JSON.stringify(out));
