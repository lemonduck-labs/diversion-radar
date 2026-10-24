/* The brief screen, shared by the workspace page and the hosted drafting function.
 *
 * A port of radar/brief/screen.py (screen_shared, name_problems, note_problems, usable_notes,
 * parse_reply, build_prompt), reading
 * radar/brief/spec/screen_rules.json and brief.schema.json unchanged. The shared cases in
 * radar/brief/spec/screen_cases.json are what this port must pass, code and path
 * (tests/screen_js.test.mjs). The private deny list of names is never part of this file:
 * the hosted function runs the reference screen with it on the server.
 *
 * A draft with any problem is never shown. Each problem is {code, path, detail}.
 *
 * Loads as a CommonJS module (Node tests), or sets globalThis.RadarScreen (the page, and
 * Deno with `import "./screen.js"`).
 */
(function (root, factory) {
  if (typeof module === 'object' && module && module.exports) module.exports = factory();
  else root.RadarScreen = factory();
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  /* ---------- regular expressions with Python's ASCII semantics ----------
     \d, \w and \b are ASCII in JavaScript without the u flag, as in Python with re.ASCII.
     \s is not: JavaScript also matches Unicode spaces. Rewrite it to the ASCII set. */
  function asciiSpaces(pattern) {
    let out = '', inClass = false;
    for (let i = 0; i < pattern.length; i++) {
      const c = pattern[i];
      if (c === '\\' && i + 1 < pattern.length) {
        const n = pattern[i + 1];
        if (n === 's') out += inClass ? '\\t\\n\\v\\f\\r ' : '[\\t\\n\\v\\f\\r ]';
        else out += c + n;
        i++;
        continue;
      }
      if (c === '[' && !inClass) inClass = true;
      else if (c === ']' && inClass) inClass = false;
      out += c;
    }
    return out;
  }
  const rx = (pattern, flags, global) => new RegExp(asciiSpaces(pattern), ((flags || '').includes('i') ? 'i' : '') + (global ? 'g' : ''));

  function compile(R) {
    const p = R.patterns, a = R.accusing, f = R.figures;
    return {
      raw: R,
      company: rx(p.company_name.pattern, p.company_name.flags, true),
      email: rx(p.email.pattern, p.email.flags, true),
      emailAllow: new Set((p.email.allow || []).map((x) => x.toLowerCase())),
      postcode: rx(p.postcode.pattern, p.postcode.flags, true),
      postcodeSkip: p.postcode.skip_if_preceded_by,
      accusing: [rx(a.pattern, a.flags, true), rx(a.extra_pattern, a.extra_flags, true)],
      hedges: a.hedges.map((x) => x.toLowerCase()),
      before: Number(a.hedge_before), after: Number(a.hedge_after),
      clause: rx(a.clause_break.pattern, a.clause_break.flags, true),
      token: rx(f.token.pattern, f.token.flags, true),
      stray: rx(f.stray.pattern, f.stray.flags, true),
      forbidden: (R.forbidden_text || []).map((x) => [x.code, x.text]),
      rank: Object.fromEntries(R.confidence_order.map((c, i) => [c, i])),
      companyExtra: rx(p.company_name_extra.pattern, p.company_name_extra.flags, true),
      capWord: rx(R.names.capitalised.pattern, R.names.capitalised.flags, true),
      acronym: rx(R.names.acronym.pattern, R.names.acronym.flags, true),
      contextWord: rx(R.names.context_word.pattern, R.names.context_word.flags, true),
      nameEndings: R.names.endings_removed.slice(),
      skipBack: R.names.skip_back, starts: R.names.starts,
      nameAllow: new Set(R.names.allow),
      instruction: rx(R.review.instruction.pattern, R.review.instruction.flags, false),
      noteId: rx(R.review.note_id.pattern, R.review.note_id.flags, false),
      numberWords: rx(f.number_words.pattern, f.number_words.flags, true),
      numberValues: Object.assign({}, f.number_words.values),
      multiples: rx(f.multiples.pattern, f.multiples.flags, true),
    };
  }

  function* all(re, text, from) {
    re.lastIndex = from || 0;
    let m;
    while ((m = re.exec(text)) !== null) {
      yield m;
      if (m[0].length === 0) re.lastIndex++;
    }
  }
  const problem = (code, path, detail) => ({ code, path, detail: detail === undefined ? '' : String(detail) });

  // Every string in obj with its path: keys joined by '.', list positions as [n].
  function walkStrings(obj, cb, path) {
    path = path || '';
    if (Array.isArray(obj)) obj.forEach((v, i) => walkStrings(v, cb, `${path}[${i}]`));
    else if (obj && typeof obj === 'object') for (const k of Object.keys(obj)) walkStrings(obj[k], cb, path ? `${path}.${k}` : k);
    else if (typeof obj === 'string') cb(path, obj);
  }

  function hedged(line, start, end, C) {
    let lo = Math.max(0, start - C.before);
    for (const b of all(C.clause, line.slice(0, start), lo)) lo = b.index + b[0].length;
    let hi = Math.min(line.length, end + C.after);
    C.clause.lastIndex = end;
    const nxt = C.clause.exec(line.slice(0, hi));
    if (nxt) hi = nxt.index;
    const window = line.slice(lo, hi).toLowerCase();
    return C.hedges.some((h) => window.includes(h));
  }

  // The wording checks of screen_rules.json on one string, line by line.
  function textProblems(text, path, C) {
    const out = [];
    for (const line of String(text).replace(/\r/g, '').split('\n')) {
      for (const [code, bad] of C.forbidden) if (line.includes(bad)) out.push(problem(code, path, JSON.stringify(bad)));
      for (const m of all(C.company, line)) out.push(problem('company_name', path, m[0]));
      for (const m of all(C.companyExtra, line)) out.push(problem('company_name', path, m[0]));
      for (const m of all(C.email, line)) if (!C.emailAllow.has(m[0].toLowerCase())) out.push(problem('email', path, m[0]));
      for (const m of all(C.postcode, line)) {
        if (m.index > 0 && line[m.index - 1] === C.postcodeSkip) continue;
        out.push(problem('postcode', path, m[0]));
      }
      for (const re of C.accusing) for (const m of all(re, line)) if (!hedged(line, m.index, m.index + m[0].length, C)) out.push(problem('accusing_language', path, m[0]));
    }
    return out;
  }

  /* ---------- possible names (screen_rules.json, names) ---------- */
  function nameRoot(word, C) {
    for (const e of C.nameEndings) if (word.endsWith(e)) word = word.slice(0, word.length - e.length);
    return word;
  }
  function startsSentence(line, i, C) {
    let j = i - 1;
    while (j >= 0 && C.skipBack.includes(line[j])) j--;
    return j < 0 || C.starts.includes(line[j]);
  }
  // The words a draft may write with capitals: the allow list and every word of the context.
  function namesAllowed(ctx, C) {
    const words = new Set(C.nameAllow);
    walkStrings(ctx, (_p, s) => { for (const m of all(C.contextWord, s)) words.add(nameRoot(m[0], C)); });
    return words;
  }
  function nameProblems(text, path, allowed, C) {
    const out = [];
    for (const line of String(text).replace(/\r/g, '').split('\n')) {
      for (const m of all(C.capWord, line)) {
        const word = nameRoot(m[0], C);
        if (allowed.has(word) || startsSentence(line, m.index, C)) continue;
        out.push(problem('possible_name', path, word));
      }
      for (const m of all(C.acronym, line)) if (!allowed.has(m[0])) out.push(problem('possible_name', path, m[0]));
    }
    return out;
  }

  // The figure tokens of a text: every token match, then every digit run left over, then the
  // value of every count written in words.
  function figureTokens(text, C) {
    text = String(text);
    const out = [], rest = text.split('');
    for (const m of all(C.token, text)) {
      const [cur, num, unit, tail] = [m[1], m[2], m[3], m[4]].map((g) => g || '');
      out.push(cur + num.replace(/,/g, '') + unit.toLowerCase() + tail.toLowerCase());
      for (let i = m.index; i < m.index + m[0].length; i++) rest[i] = ' ';
    }
    for (const m of all(C.stray, rest.join(''))) out.push(m[0]);
    for (const m of all(C.numberWords, text)) out.push(C.numberValues[m[0].toLowerCase()]);
    return out;
  }
  function tokensOf(obj, C) {
    const s = new Set();
    walkStrings(obj, (_p, str) => { for (const t of figureTokens(str, C)) s.add(t); });
    return s;
  }

  // Every claim in a draft that matches the schema, with its path.
  function claims(d) {
    const out = [['headline', d.headline]];
    for (const part of ['uk', 'onward']) d.what_rose[part].forEach((c, i) => out.push([`what_rose.${part}[${i}]`, c]));
    d.why_it_may_be_ordinary.forEach((c, i) => out.push([`why_it_may_be_ordinary[${i}]`, c]));
    out.push(['linked_cases.note', d.linked_cases.note]);
    d.questions_to_check.forEach((q, i) => { if (Object.prototype.hasOwnProperty.call(q, 'why_here')) out.push([`questions_to_check[${i}].why_here`, q.why_here]); });
    (d.responds_to_review || []).forEach((a, i) => out.push([`responds_to_review[${i}].change`, a.change]));
    return out;
  }

  /* ---------- reviewer notes (screen_rules.json, review) ----------
     A note never extends the context: its words are not allowed names, its figures are not
     citable. A note that fails these checks is held back from the prompt. */
  function noteProblems(text, ctx, path, C) {
    text = String(text);
    const p = path || 'note';
    const out = textProblems(text, p, C).concat(nameProblems(text, p, namesAllowed(ctx, C), C));
    for (const line of text.replace(/\r/g, '').split('\n')) {
      const m = C.instruction.exec(line);
      if (m) { out.push(problem('planted_instruction', p, m[0].slice(0, 80))); break; }
    }
    if (codeLen(text) > Number(C.raw.review.max_note_length)) out.push(problem('note_too_long', p, String(codeLen(text))));
    return dedupe(out);
  }
  // The notes as given: at most max_notes, unique ids matching note_id, each with a text.
  function checkReview(review, C) {
    const notes = Array.isArray(review) ? review.slice() : [];
    if (notes.length > Number(C.raw.review.max_notes)) throw new Error('at most ' + C.raw.review.max_notes + ' reviewer notes');
    const ids = notes.map((n) => (n && typeof n === 'object' ? n.id : null));
    if (ids.some((i) => typeof i !== 'string' || !C.noteId.test(i)) || new Set(ids).size !== ids.length) throw new Error('reviewer notes need unique ids review-1 to review-5');
    if (notes.some((n) => typeof n.text !== 'string')) throw new Error('every reviewer note needs a text');
    return notes;
  }
  function usableNotes(review, ctx, C) {
    const usable = [], held = [];
    for (const n of checkReview(review, C)) {
      const probs = noteProblems(n.text, ctx, 'note', C);
      if (probs.length) held.push(Object.assign({}, n, { problems: probs })); else usable.push(n);
    }
    return { usable, held };
  }
  function citable(ctx) {
    const items = new Map();
    for (const x of ctx.facts) items.set(x.id, x);
    for (const x of ctx.limits) items.set(x.id, x);
    for (const x of ctx.cases) items.set(x.id, x);
    return items;
  }

  /* ---------- JSON Schema (draft 2020-12), the keywords the brief schema uses ----------
     Errors are reported as jsonschema reports them: at the instance's path, keyword by
     keyword in the schema's own order, then sorted by path. */
  const pathText = (parts) => parts.reduce((s, p) => (typeof p === 'number' ? `${s}[${p}]` : s ? `${s}.${p}` : String(p)), '');
  const codeLen = (s) => Array.from(s).length;
  function isType(v, t) {
    switch (t) {
      case 'object': return v !== null && typeof v === 'object' && !Array.isArray(v);
      case 'array': return Array.isArray(v);
      case 'string': return typeof v === 'string';
      case 'number': return typeof v === 'number';
      case 'integer': return typeof v === 'number' && Number.isInteger(v);
      case 'boolean': return typeof v === 'boolean';
      case 'null': return v === null;
      default: return false;
    }
  }
  function deepEqual(a, b) {
    if (a === b) return true;
    if (typeof a !== typeof b || a === null || b === null || typeof a !== 'object') return false;
    if (Array.isArray(a) !== Array.isArray(b)) return false;
    if (Array.isArray(a)) return a.length === b.length && a.every((x, i) => deepEqual(x, b[i]));
    const ka = Object.keys(a), kb = Object.keys(b);
    return ka.length === kb.length && ka.every((k) => Object.prototype.hasOwnProperty.call(b, k) && deepEqual(a[k], b[k]));
  }
  function resolveRef(root, ref) {
    if (typeof ref !== 'string' || !ref.startsWith('#')) throw new Error('unsupported $ref ' + ref);
    let node = root;
    for (const part of ref.slice(1).split('/').filter(Boolean)) node = node[part.replace(/~1/g, '/').replace(/~0/g, '~')];
    return node;
  }
  function schemaErrors(schema, v, path, out, root) {
    if (schema === true || schema === undefined) return;
    if (schema === false) { out.push([path, 'false']); return; }
    for (const k of Object.keys(schema)) {
      const s = schema[k];
      switch (k) {
        case '$ref': schemaErrors(resolveRef(root, s), v, path, out, root); break;
        case 'type': if (!(Array.isArray(s) ? s : [s]).some((t) => isType(v, t))) out.push([path, 'type']); break;
        case 'const': if (!deepEqual(v, s)) out.push([path, 'const']); break;
        case 'enum': if (!s.some((x) => deepEqual(v, x))) out.push([path, 'enum']); break;
        case 'minLength': if (typeof v === 'string' && codeLen(v) < s) out.push([path, 'minLength']); break;
        case 'maxLength': if (typeof v === 'string' && codeLen(v) > s) out.push([path, 'maxLength']); break;
        case 'pattern': if (typeof v === 'string' && !new RegExp(s).test(v)) out.push([path, 'pattern']); break;
        case 'minItems': if (Array.isArray(v) && v.length < s) out.push([path, 'minItems']); break;
        case 'maxItems': if (Array.isArray(v) && v.length > s) out.push([path, 'maxItems']); break;
        case 'uniqueItems':
          if (s && Array.isArray(v) && v.some((x, i) => v.slice(i + 1).some((y) => deepEqual(x, y)))) out.push([path, 'uniqueItems']);
          break;
        case 'items': if (Array.isArray(v)) v.forEach((x, i) => schemaErrors(s, x, path.concat([i]), out, root)); break;
        case 'required':
          if (isType(v, 'object')) for (const r of s) if (!Object.prototype.hasOwnProperty.call(v, r)) out.push([path, 'required']);
          break;
        case 'properties':
          if (isType(v, 'object')) for (const p of Object.keys(s)) if (Object.prototype.hasOwnProperty.call(v, p)) schemaErrors(s[p], v[p], path.concat([p]), out, root);
          break;
        case 'additionalProperties':
          if (isType(v, 'object')) {
            const known = new Set(Object.keys(schema.properties || {}));
            const extra = Object.keys(v).filter((x) => !known.has(x));
            if (extra.length) {
              if (s === false) out.push([path, 'additionalProperties']);
              else if (s && typeof s === 'object') for (const x of extra) schemaErrors(s, v[x], path.concat([x]), out, root);
            }
          }
          break;
        default: break; // annotations: title, description, $defs, $schema
      }
    }
  }
  function schemaProblems(draft, schema) {
    const raw = [];
    schemaErrors(schema, draft, [], raw, schema);
    const key = (parts) => parts.map(String);
    const cmp = (a, b) => {
      const x = key(a[0]), y = key(b[0]);
      for (let i = 0; i < Math.min(x.length, y.length); i++) if (x[i] !== y[i]) return x[i] < y[i] ? -1 : 1;
      return x.length - y.length;
    };
    return raw.map((e, i) => [e, i]).sort((a, b) => cmp(a[0], b[0]) || a[1] - b[1]).map(([e]) => problem('schema', pathText(e[0]), e[1]));
  }

  // A model reply as a draft: one JSON object, optionally inside one Markdown code fence.
  function parseReply(reply) {
    let s = String(reply).trim();
    const m = /^```[A-Za-z0-9_-]*[ \t]*\n([\s\S]*)\n[ \t]*```$/.exec(s);
    if (m) s = m[1].trim();
    let obj;
    try { obj = JSON.parse(s); } catch (e) { return { ok: false, problem: problem('not_json', '', 'the reply is not JSON') }; }
    if (!isType(obj, 'object')) return { ok: false, problem: problem('not_json', '', 'the reply is not a JSON object') };
    return { ok: true, draft: obj };
  }

  function dedupe(list) {
    const seen = new Set(), out = [];
    for (const p of list) { const k = p.code + '\u0000' + p.path; if (!seen.has(k)) { seen.add(k); out.push(p); } }
    return out;
  }

  // The checks of screen_rules.json: what radar/brief/screen.py's screen_shared runs.
  function screenShared(draft, ctx, C, schema, review) {
    const noteIds = checkReview(review, C).map((n) => n.id);
    if (!isType(draft, 'object')) return [problem('not_json', '', 'the draft is not a JSON object')];
    const errs = schemaProblems(draft, schema);
    if (errs.length) return errs;
    const raw = C.raw, out = [];
    if (draft.series !== ctx.series) out.push(problem('series_mismatch', 'series', draft.series));
    if (draft.run !== ctx.run) out.push(problem('run_mismatch', 'run', draft.run));
    if (draft.house_line !== raw.house_line) out.push(problem('house_line', 'house_line', draft.house_line.slice(0, 80)));
    if (draft.ogl_line !== raw.ogl_line) out.push(problem('ogl_line', 'ogl_line', draft.ogl_line.slice(0, 80)));
    if (!draft.headline.text.toLowerCase().includes(raw.headline_must_contain.toLowerCase())) out.push(problem('headline_not_hedged', 'headline.text', draft.headline.text.slice(0, 80)));
    const allowed = namesAllowed(ctx, C);
    walkStrings(draft, (p, s) => {
      for (const x of textProblems(s, p, C)) out.push(x);
      for (const x of nameProblems(s, p, allowed, C)) out.push(x);
    });
    const items = citable(ctx);
    const inContext = tokensOf(ctx, C);
    const free = tokensOf(raw.figures.free_fields.map((k) => (ctx[k] === undefined ? '' : ctx[k])), C);
    for (const [path, c] of claims(draft)) {
      const cited = [];
      const answer = path.startsWith('responds_to_review[');
      c.cites.forEach((cid, i) => {
        if (items.has(cid)) cited.push(items.get(cid));
        else if (!(answer && noteIds.includes(cid))) out.push(problem('unknown_fact', `${path}.cites[${i}]`, cid));
      });
      const allowed = new Set([...free, ...tokensOf(cited, C)]);
      for (const tok of figureTokens(c.text, C)) if (!allowed.has(tok)) out.push(problem(inContext.has(tok) ? 'uncited_figure' : 'invented_figure', `${path}.text`, tok));
      for (const m of all(C.multiples, String(c.text))) out.push(problem('figure_in_words', `${path}.text`, m[0]));
      if (cited.length) {
        const floor = Math.min(...cited.map((x) => C.rank[x.confidence]));
        if (C.rank[c.confidence] > floor) out.push(problem('confidence_above_source', `${path}.confidence`, `${c.confidence} above ${raw.confidence_order[floor]}`));
      }
    }
    const limitIds = new Set(ctx.limits.map((x) => x.id));
    draft.limits.forEach((lid, i) => { if (!limitIds.has(lid)) out.push(problem('unknown_fact', `limits[${i}]`, lid)); });
    const caseIds = ctx.cases.map((c) => c.case_id);
    const got = draft.linked_cases.case_ids;
    got.forEach((cid, i) => { if (!caseIds.includes(cid)) out.push(problem('unknown_case', `linked_cases.case_ids[${i}]`, cid)); });
    const missing = caseIds.filter((c) => !got.includes(c));
    if (missing.length) out.push(problem('cases_missing', 'linked_cases.case_ids', missing.join(', ')));
    const flags = new Map(ctx.red_flags.map((f) => [f.id, f]));
    draft.questions_to_check.forEach((q, i) => {
      const f = flags.get(q.red_flag);
      if (!f) out.push(problem('unknown_red_flag', `questions_to_check[${i}].red_flag`, q.red_flag));
      else if (q.question !== f.question) out.push(problem('red_flag_text_changed', `questions_to_check[${i}].question`, q.red_flag));
    });
    const seen = new Set();
    (draft.responds_to_review || []).forEach((a, i) => {
      const nid = a.note;
      if (!noteIds.includes(nid)) out.push(problem('review_unknown', `responds_to_review[${i}].note`, nid));
      else if (seen.has(nid)) out.push(problem('review_duplicate', `responds_to_review[${i}].note`, nid));
      seen.add(nid);
      if (!a.change.cites.includes(nid)) out.push(problem('review_not_cited', `responds_to_review[${i}].change.cites`, nid));
      if (a.change.text.trim() === raw.review.placeholder) out.push(problem('review_placeholder', `responds_to_review[${i}].change.text`, nid));
    });
    const unanswered = noteIds.filter((n) => !seen.has(n));
    if (unanswered.length) out.push(problem('review_unanswered', 'responds_to_review', unanswered.join(', ')));
    return dedupe(out);
  }

  // The drafting prompt from spec/prompt.md: {system, user}, filled as radar/brief/prompt.py fills it.
  function buildPrompt(promptText, R, schema, ctx, review, lessons) {
    const marks = [...String(promptText).matchAll(/^=== (system|user) ===$/gm)];
    if (marks.map((m) => m[1]).join() !== 'system,user') throw new Error('prompt.md needs a system section and then a user section');
    const strip = (s) => s.replace(/^\n+|\n+$/g, '');
    const parts = {
      system: strip(promptText.slice(marks[0].index + marks[0][0].length, marks[1].index)),
      user: strip(promptText.slice(marks[1].index + marks[1][0].length)),
    };
    const vals = {
      house_line: R.house_line, ogl_line: R.ogl_line, headline_phrase: R.headline_must_contain,
      blocked_words: R.prompt_word_examples.join(', '),
      schema: JSON.stringify(schema, null, 1), context: JSON.stringify(ctx, null, 1),
      review: JSON.stringify(Array.isArray(review) ? review : [], null, 1),
      lessons: JSON.stringify(Array.isArray(lessons) ? lessons : [], null, 1),
    };
    for (const k of Object.keys(parts)) {
      parts[k] = parts[k].replace(/\{\{([a-z_]+)\}\}/g, (m, name) => {
        if (!(name in vals)) throw new Error('unknown placeholder ' + name);
        return vals[name];
      });
    }
    return parts;
  }

  return { compile, textProblems, nameProblems, namesAllowed, noteProblems, checkReview, usableNotes, figureTokens, tokensOf, walkStrings, claims, citable, schemaProblems, parseReply, screenShared, buildPrompt, problem, asciiSpaces };
});
