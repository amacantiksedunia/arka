/*
 * Runtime mini untuk template prototipe ARKA.
 * Mendukung sintaks yang dipakai prototipe:
 *   {{ path.ke.nilai }}          -> teks / atribut
 *   <sc-if value="{{ x }}">      -> tampil bila truthy
 *   <sc-for list="{{ xs }}" as="item">
 *   onclick / onchange / onkeydown="{{ fungsi }}"
 *   style-hover="..."            -> gaya saat hover
 * Render memakai virtual DOM sederhana + patch, sehingga fokus input tidak hilang.
 */
'use strict';

const DC = (() => {
  const VOID = new Set(['input', 'img', 'br', 'hr', 'meta', 'link', 'source', 'col', 'area', 'wbr']);
  const SVG_NS = 'http://www.w3.org/2000/svg';
  const SVG_TAGS = new Set(['svg', 'path', 'circle', 'rect', 'line', 'polyline', 'polygon', 'g', 'defs', 'linearGradient', 'lineargradient', 'stop', 'text', 'ellipse']);
  const decoder = document.createElement('textarea');
  const decode = (s) => (s.indexOf('&') < 0 ? s : (decoder.innerHTML = s, decoder.value));

  /* ---------- parser: string -> pohon {tag, attrs, children} */
  function parse(src) {
    const root = { tag: '#root', attrs: {}, children: [] };
    const stack = [root];
    const re = /<!--[\s\S]*?-->|<\/([a-zA-Z][\w-]*)\s*>|<([a-zA-Z][\w-]*)((?:\s+[^\s=>\/]+(?:\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>]+))?)*)\s*(\/?)>|([^<]+)/g;
    const attrRe = /([^\s=>\/]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+)))?/g;
    let m;
    while ((m = re.exec(src))) {
      const top = stack[stack.length - 1];
      if (m[0].startsWith('<!--')) continue;
      if (m[1]) {                                   // tag penutup
        const name = m[1];
        for (let i = stack.length - 1; i > 0; i--) if (stack[i].tag === name) { stack.length = i; break; }
      } else if (m[2]) {                            // tag pembuka
        const tag = m[2], attrs = {};
        let a; attrRe.lastIndex = 0;
        while ((a = attrRe.exec(m[3] || ''))) attrs[a[1]] = decode(a[2] ?? a[3] ?? a[4] ?? '');
        const svg = top.svg || tag === 'svg';
        const node = { tag, attrs, children: [], svg };
        top.children.push(node);
        if (!m[4] && !VOID.has(tag.toLowerCase())) stack.push(node);
      } else if (m[5]) {
        const text = decode(m[5]);
        if (text.trim() || /\S/.test(text) || top.children.length) top.children.push(text.replace(/\s*\n\s*/g, ' '));
      }
    }
    return root;
  }

  /* ---------- evaluasi binding */
  function lookup(path, scope) {
    path = path.trim();
    if (path === 'true') return true;
    if (path === 'false') return false;
    const parts = path.split('.');
    let v;
    for (let i = scope.length - 1; i >= 0; i--) if (scope[i] && parts[0] in scope[i]) { v = scope[i][parts[0]]; break; }
    for (let j = 1; j < parts.length && v != null; j++) v = v[parts[j]];
    return v;
  }
  const ONE = /^\s*\{\{\s*([\w.]+)\s*\}\}\s*$/;
  function interp(str, scope) {
    const one = str.match(ONE);
    if (one) return lookup(one[1], scope);
    return str.replace(/\{\{\s*([\w.]+)\s*\}\}/g, (_, p) => { const v = lookup(p, scope); return v == null ? '' : v; });
  }

  /* ---------- gaya hover -> kelas CSS */
  const hoverCache = new Map();
  let hoverSheet;
  function hoverClass(css) {
    if (hoverCache.has(css)) return hoverCache.get(css);
    if (!hoverSheet) { hoverSheet = document.createElement('style'); document.head.appendChild(hoverSheet); }
    const cls = 'dch' + hoverCache.size;
    const decl = css.split(';').filter((d) => d.trim()).map((d) => d.trim() + ' !important').join(';');
    hoverSheet.appendChild(document.createTextNode(`.${cls}:hover{${decl}}`));
    hoverCache.set(css, cls);
    return cls;
  }

  /* ---------- pohon template + data -> vnode */
  function build(node, scope, out) {
    if (typeof node === 'string') {
      const s = node.includes('{{') ? String(interp(node, scope) ?? '') : node;
      if (s !== '') out.push(s);
      return;
    }
    if (node.tag === 'sc-if') {
      if (lookup(node.attrs.value.replace(/[{}]/g, ''), scope)) node.children.forEach((c) => build(c, scope, out));
      return;
    }
    if (node.tag === 'sc-for') {
      const list = lookup(node.attrs.list.replace(/[{}]/g, ''), scope) || [];
      const as = node.attrs.as || 'item';
      list.forEach((item, i) => node.children.forEach((c) => build(c, [...scope, { [as]: item, [as + 'Index']: i }], out)));
      return;
    }
    if (node.tag === '#root') { node.children.forEach((c) => build(c, scope, out)); return; }
    const v = { tag: node.tag, svg: node.svg, attrs: {}, on: {}, children: [] };
    for (const [k, raw] of Object.entries(node.attrs)) {
      if (k.startsWith('hint-')) continue;
      const val = raw.includes('{{') ? interp(raw, scope) : raw;
      if (/^on/.test(k)) { if (typeof val === 'function') v.on[k.slice(2).toLowerCase()] = val; continue; }
      if (k === 'style-hover') { v.attrs.class = ((v.attrs.class || '') + ' ' + hoverClass(val)).trim(); continue; }
      if (val === false || val == null) continue;
      v.attrs[k] = val === true ? '' : String(val);
    }
    node.children.forEach((c) => build(c, scope, v.children));
    out.push(v);
  }

  /* ---------- patch DOM */
  function create(v) {
    if (typeof v === 'string') return document.createTextNode(v);
    const el = v.svg ? document.createElementNS(SVG_NS, v.tag) : document.createElement(v.tag);
    el.__h = {};
    update(el, v, { attrs: {}, on: {} });
    v.children.forEach((c) => el.appendChild(create(c)));
    return el;
  }
  const PROP_VALUE = new Set(['input', 'select', 'textarea']);
  function update(el, v, old) {
    for (const k in old.attrs) if (!(k in v.attrs)) el.removeAttribute(k);
    for (const [k, val] of Object.entries(v.attrs)) {
      if (k === 'value' && PROP_VALUE.has(v.tag)) continue;
      if (old.attrs[k] !== val) el.setAttribute(k, val);
    }
    // event: satu listener per jenis, handler terbaru disimpan di el.__h
    el.__h = el.__h || {};
    for (const [evt, fn] of Object.entries(v.on)) {
      if (!el.__h[evt]) {
        const names = evt === 'change' ? ['input', 'change'] : [evt];
        names.forEach((n) => el.addEventListener(n, (e) => { const f = el.__h[evt]; if (f) { if (evt === 'click' && el.tagName === 'A') e.preventDefault(); f(e); } }));
      }
      el.__h[evt] = fn;
    }
    for (const evt in el.__h) if (!(evt in v.on)) el.__h[evt] = null;
    if (PROP_VALUE.has(v.tag) && 'value' in v.attrs) {
      const want = v.attrs.value;
      if (v.tag === 'select') queueMicrotask(() => { if (el.value !== want) el.value = want; });
      else if (el.value !== want) el.value = want;
    }
  }
  function patch(parent, newKids, oldKids) {
    const dom = parent.childNodes;
    for (let i = 0; i < newKids.length; i++) {
      const n = newKids[i], o = oldKids[i], d = dom[i];
      if (o === undefined || !d) { parent.appendChild(create(n)); continue; }
      if (typeof n === 'string' || typeof o === 'string') {
        if (typeof n === 'string' && typeof o === 'string') { if (n !== o) d.nodeValue = n; }
        else parent.replaceChild(create(n), d);
        continue;
      }
      if (n.tag !== o.tag || n.svg !== o.svg) { parent.replaceChild(create(n), d); continue; }
      update(d, n, o);
      patch(d, n.children, o.children);
    }
    while (parent.childNodes.length > newKids.length) parent.removeChild(parent.lastChild);
  }

  /* ---------- kelas dasar logika (setara DCLogic prototipe) */
  class Logic {
    constructor() { this.state = this.state || {}; this._q = false; }
    setState(u) {
      const patchObj = typeof u === 'function' ? u(this.state) : u;
      this.state = { ...this.state, ...patchObj };
      this._schedule();
    }
    _schedule() { if (this._q) return; this._q = true; requestAnimationFrame(() => { this._q = false; this._render(); }); }
  }

  function mount(tplSource, logic, el) {
    const tree = parse(tplSource);
    let prev = [];
    logic._render = () => {
      const out = [];
      build(tree, [logic.renderVals()], out);
      patch(el, out, prev);
      prev = out;
      logic.afterRender && logic.afterRender();
    };
    logic._render();
  }

  return { parse, mount, Logic };
})();
