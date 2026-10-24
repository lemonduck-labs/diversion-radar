/* A stand-in for the dashboard runtime, so the two dashboards run as static pages.
 *
 * The radar dashboard (demo/radar/index.html) and the TA market picture (ta-market's
 * demo/ta/index.html) were written for Claude's Dashboard artifact type, which gives a page a
 * global `dash`. This file gives the same calls the two pages make, over JSON files published
 * beside the page, and nothing else:
 *
 *   dash.data(id)       {status, data, columns, message, refreshing}: "loading" until
 *                       data/<id>.json arrives, then "ok", or "error" if it does not load
 *   dash.onData(fn)     calls fn now, and again when data arrives, when the parameters change
 *                       and when the page's width changes
 *   dash.colors         eight series colours, as CSS variables (assets/site.css), so they follow
 *                       the light or dark theme
 *   dash.params()       the page's parameters, kept in the address's query string
 *   dash.setParams(p)   merges p into them (a null value removes one) and redraws
 *   dash.resetParams()  clears them and redraws
 *   dash.setLink(id)    puts #id in the address, for the view being shown
 *
 * The datasets to load are named in this script tag's data-sources attribute. The only requests
 * are for files on this site; nothing is sent anywhere.
 */
(function () {
  'use strict';
  var me = document.currentScript;
  var ids = ((me && me.getAttribute('data-sources')) || '').split(',').map(function (s) { return s.trim(); }).filter(Boolean);
  var base = (me && me.getAttribute('data-base')) || 'data/';
  var store = Object.create(null);
  var subs = [];
  var failed = [];

  ids.forEach(function (id) { store[id] = { status: 'loading', data: null, columns: [], message: '', refreshing: false }; });

  var queued = false;
  function fire() {
    if (queued) return;
    queued = true;
    setTimeout(function () {
      queued = false;
      subs.slice().forEach(function (fn) {
        try { fn(); } catch (e) { console.error(e); }
      });
    }, 0);
  }

  function readParams() {
    var out = {};
    new URLSearchParams(location.search).forEach(function (v, k) { out[k] = v; });
    return out;
  }
  function writeParams(p) {
    var q = new URLSearchParams();
    Object.keys(p).sort().forEach(function (k) { if (p[k] !== null && p[k] !== undefined && p[k] !== '') q.set(k, String(p[k])); });
    var s = q.toString();
    try { history.replaceState(null, '', location.pathname + (s ? '?' + s : '') + location.hash); } catch (e) { /* a sandboxed view */ }
  }

  function notice() {
    var box = document.getElementById('site-notice');
    if (!box || !failed.length) return;
    box.textContent = 'Some of the data for this page did not load (' + failed.join(', ') + '). Reload the page; the figures marked with an ellipsis are the ones missing.';
    box.hidden = false;
  }

  function load(id) {
    return fetch(base + encodeURIComponent(id) + '.json', { credentials: 'same-origin' })
      .then(function (r) {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
      })
      .then(function (data) {
        var first = Array.isArray(data) && data.length && data[0] && typeof data[0] === 'object' ? data[0] : null;
        store[id] = { status: 'ok', data: data, columns: first ? Object.keys(first) : [], message: '', refreshing: false };
      })
      .catch(function (e) {
        store[id] = { status: 'error', data: null, columns: [], message: 'The dataset did not load: ' + e.message, refreshing: false };
        failed.push(id);
        console.error('dataset ' + id + ': ' + e.message);
      })
      .then(fire);
  }

  var width = window.innerWidth;
  var resizeTimer = null;
  window.addEventListener('resize', function () {
    if (window.innerWidth === width) return;
    width = window.innerWidth;
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(fire, 150);
  });

  var dash = {
    colors: [1, 2, 3, 4, 5, 6, 7, 8].map(function (i) { return 'var(--series-' + i + ')'; }),
    data: function (id) {
      return store[id] || { status: 'error', data: null, columns: [], message: 'No dataset called ' + id + ' on this page.', refreshing: false };
    },
    onData: function (fn) {
      subs.push(fn);
      try { fn(); } catch (e) { console.error(e); }
      return function () { var i = subs.indexOf(fn); if (i >= 0) subs.splice(i, 1); };
    },
    params: function () { return readParams(); },
    setParams: function (p) {
      var cur = readParams();
      Object.keys(p || {}).forEach(function (k) { if (p[k] === null || p[k] === undefined) delete cur[k]; else cur[k] = String(p[k]); });
      writeParams(cur);
      fire();
    },
    resetParams: function () { writeParams({}); fire(); },
    setLink: function (id) {
      try { history.replaceState(null, '', location.pathname + location.search + (id ? '#' + encodeURIComponent(id) : '')); } catch (e) { /* a sandboxed view */ }
    }
  };
  window.dash = dash;

  Promise.all(ids.map(load)).then(notice);
})();
