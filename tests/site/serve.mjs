// A small static server that stands in for Netlify, for the smoke test and the walkthroughs: it
// serves a built site, sends the headers its _headers file gives each path (and fails if two
// rules set the same header for a path), serves a folder's index.html for /radar as well as
// /radar/, and 404.html for a missing path.
import http from 'node:http';
import { readFile, stat } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import path from 'node:path';

const TYPES = {
  '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.mjs': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8', '.json': 'application/json; charset=utf-8', '.md': 'text/markdown; charset=utf-8',
  '.txt': 'text/plain; charset=utf-8', '.csv': 'text/csv; charset=utf-8', '.vtt': 'text/vtt; charset=utf-8',
  '.svg': 'image/svg+xml', '.png': 'image/png', '.ico': 'image/x-icon', '.mp4': 'video/mp4', '.webm': 'video/webm',
};

export function parseHeaders(text) {
  const rules = [];
  for (const raw of text.split('\n')) {
    if (!raw.trim() || raw.trim().startsWith('#')) continue;
    if (!/^[ \t]/.test(raw)) rules.push([raw.trim(), []]);
    else { const i = raw.indexOf(':'); rules[rules.length - 1][1].push([raw.slice(0, i).trim(), raw.slice(i + 1).trim()]); }
  }
  return rules;
}

export function headersFor(rules, p) {
  const out = {};
  for (const [pat, hs] of rules) {
    const match = pat === '/*' || pat === p || (pat.endsWith('/*') && (p + '/').startsWith(pat.slice(0, -1)));
    if (!match) continue;
    for (const [k, v] of hs) {
      if (k in out) throw new Error(`_headers sets ${k} twice for ${p}`);
      out[k] = v;
    }
  }
  return out;
}

export async function serve(root) {
  root = path.resolve(root);
  const rules = parseHeaders(await readFile(path.join(root, '_headers'), 'utf8'));
  const served = [];
  const server = http.createServer(async (req, res) => {
    const url = new URL(req.url, 'http://x');
    const p = decodeURIComponent(url.pathname);
    let file = path.join(root, p);
    if (!file.startsWith(root)) { res.writeHead(400).end(); return; }
    try {
      if ((await stat(file)).isDirectory()) file = path.join(file, 'index.html');
    } catch { /* missing: 404 below */ }
    let status = 200;
    if (!existsSync(file) || path.basename(file).startsWith('_')) { status = 404; file = path.join(root, '404.html'); }
    served.push([p, status]);
    const body = await readFile(file);
    const hs = headersFor(rules, p);
    res.writeHead(status, { 'Content-Type': TYPES[path.extname(file)] || 'application/octet-stream', 'Cache-Control': 'no-store', ...hs });
    res.end(body);
  });
  await new Promise((r) => server.listen(0, '127.0.0.1', r));
  return { origin: `http://127.0.0.1:${server.address().port}`, served, close: () => new Promise((r) => server.close(r)) };
}
