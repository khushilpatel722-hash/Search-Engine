/* Privata front-end (vanilla JavaScript). Talks only to this local Flask server. */
(function () {
  'use strict';
  const $ = (s, r) => (r || document).querySelector(s);
  const $$ = (s, r) => Array.from((r || document).querySelectorAll(s));
  const page = document.body.dataset.page;
  const root = document.documentElement;

  /* ---------- helpers ---------- */
  function el(tag, cls, text) {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined) n.textContent = text;           // textContent = safe, never HTML
    return n;
  }
  function icon(name) {
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('class', 'i');
    const use = document.createElementNS('http://www.w3.org/2000/svg', 'use');
    use.setAttribute('href', '#i-' + name);
    svg.appendChild(use);
    return svg;
  }
  async function api(url, opts) {
    let res;
    try { res = await fetch(url, opts); }
    catch (e) { throw new Error('Cannot reach the local Privata server. Is "python app.py" still running?'); }
    let data = null;
    try { data = await res.json(); } catch (e) { /* not JSON */ }
    if (!res.ok || !data || data.ok === false) throw new Error((data && data.error) || 'Request failed (' + res.status + ').');
    return data;
  }
  function toast(msg, kind) {
    const t = el('div', 'toast ' + (kind || ''), msg);
    $('#toasts').appendChild(t);
    setTimeout(() => t.remove(), kind === 'err' ? 6500 : 3800);
  }
  const fmtBytes = n => n < 1024 ? n + ' B' : n < 1048576 ? (n / 1024).toFixed(1) + ' KB' : (n / 1048576).toFixed(1) + ' MB';
  const fmtNum = n => Number(n || 0).toLocaleString();
  function fmtDate(ts) {
    if (!ts) return 'Never';
    const d = new Date(ts * 1000), now = new Date();
    const time = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    return d.toDateString() === now.toDateString() ? 'Today, ' + time : d.toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' });
  }
  const debounce = (fn, ms) => { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; };
  const store = {
    get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* ignore */ } }
  };

  /* ---------- theme + animation toggles ---------- */
  function paintToggles() {
    const dark = root.getAttribute('data-theme') === 'dark';
    $('#themeLbl').textContent = dark ? 'Light Mode' : 'Dark Mode';
    $('#themeIcon').firstElementChild.setAttribute('href', dark ? '#i-sun' : '#i-moon');
    $('#animLbl').textContent = 'Animation: ' + (root.classList.contains('no-anim') ? 'Off' : 'On');
  }
  $('#themeBtn').addEventListener('click', () => {
    const next = root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
    root.setAttribute('data-theme', next); store.set('privata-theme', next);
    paintToggles(); readParticleColor();
  });
  $('#animBtn').addEventListener('click', () => {
    const off = root.classList.toggle('no-anim');
    store.set('privata-anim', off ? 'off' : 'on');
    paintToggles(); off ? stopBg() : startBg();
  });
  $('#menuBtn').addEventListener('click', () => {
    const open = $('#menu').classList.toggle('open');
    $('#menuBtn').setAttribute('aria-expanded', open);
  });

  /* ---------- lightweight canvas background (pauses when hidden / disabled) ---------- */
  const canvas = $('#bg'), ctx = canvas.getContext('2d');
  let pts = [], raf = 0, W = 0, H = 0, pColor = 'rgba(91,95,240,.45)';
  function readParticleColor() { pColor = getComputedStyle(root).getPropertyValue('--particle').trim() || pColor; }
  function resizeBg() {
    W = canvas.width = innerWidth; H = canvas.height = innerHeight;
    const n = Math.min(60, Math.floor(W * H / 24000));
    pts = Array.from({ length: n }, () => ({ x: Math.random() * W, y: Math.random() * H, vx: (Math.random() - .5) * .28, vy: (Math.random() - .5) * .28, r: 1 + Math.random() * 1.4 }));
  }
  function frame() {
    ctx.clearRect(0, 0, W, H);
    ctx.fillStyle = pColor; ctx.strokeStyle = pColor; ctx.lineWidth = .6;
    for (let i = 0; i < pts.length; i++) {
      const p = pts[i];
      p.x += p.vx; p.y += p.vy;
      if (p.x < 0 || p.x > W) p.vx *= -1;
      if (p.y < 0 || p.y > H) p.vy *= -1;
      ctx.beginPath(); ctx.arc(p.x, p.y, p.r, 0, 6.283); ctx.fill();
      for (let j = i + 1; j < pts.length; j++) {
        const q = pts[j], dx = p.x - q.x, dy = p.y - q.y, d = dx * dx + dy * dy;
        if (d < 12000) { ctx.globalAlpha = 1 - d / 12000; ctx.beginPath(); ctx.moveTo(p.x, p.y); ctx.lineTo(q.x, q.y); ctx.stroke(); ctx.globalAlpha = 1; }
      }
    }
    raf = requestAnimationFrame(frame);
  }
  function startBg() { if (!raf && !root.classList.contains('no-anim') && !document.hidden) { resizeBg(); raf = requestAnimationFrame(frame); } }
  function stopBg() { cancelAnimationFrame(raf); raf = 0; ctx.clearRect(0, 0, W, H); }
  addEventListener('resize', debounce(() => { if (raf) resizeBg(); }, 200));
  document.addEventListener('visibilitychange', () => document.hidden ? stopBg() : startBg());
  readParticleColor(); paintToggles(); startBg();

  /* ---------- search box with suggestions ---------- */
  const form = $('#searchForm');
  let onSearch = null;                       // set by the search page
  function initSearchBox() {
    if (!form) return;
    const input = $('#q'), list = $('#suggest'), clear = $('#clearBtn');
    let items = [], active = -1;
    const close = () => { list.hidden = true; active = -1; };
    function paint() {
      list.replaceChildren();
      items.forEach((text, i) => {
        const li = el('li', i === active ? 'on' : '');
        li.setAttribute('role', 'option');
        li.append(icon('search'), el('span', '', text));
        li.addEventListener('mousedown', e => { e.preventDefault(); input.value = text; close(); submit(); });
        list.appendChild(li);
      });
      list.hidden = !items.length;
    }
    const fetchSuggest = debounce(async () => {
      const q = input.value.trim();
      if (q.length < 2) { items = []; return paint(); }
      try { items = (await api('/api/suggest?q=' + encodeURIComponent(q))).suggestions; } catch (e) { items = []; }
      active = -1; paint();
    }, 120);
    function submit() {
      if (onSearch) onSearch(input.value);
      else form.submit();
    }
    input.addEventListener('input', () => { if (clear) clear.hidden = !input.value; fetchSuggest(); });
    input.addEventListener('keydown', e => {
      if (e.key === 'ArrowDown' && items.length) { e.preventDefault(); active = (active + 1) % items.length; paint(); }
      else if (e.key === 'ArrowUp' && items.length) { e.preventDefault(); active = (active - 1 + items.length) % items.length; paint(); }
      else if (e.key === 'Enter' && active >= 0) { e.preventDefault(); input.value = items[active]; close(); submit(); }
      else if (e.key === 'Escape') close();
    });
    input.addEventListener('blur', () => setTimeout(close, 120));
    form.addEventListener('submit', e => { if (onSearch) { e.preventDefault(); close(); onSearch(input.value); } });
    if (clear) clear.addEventListener('click', () => { input.value = ''; clear.hidden = true; close(); input.focus(); if (onSearch) onSearch(''); });
    if (page === 'home' || page === 'search') input.focus();
  }

  /* ---------- recent searches ---------- */
  async function loadRecent(target, onPick) {
    let recent = [];
    try { recent = (await api('/api/recent')).recent; } catch (e) { /* ignore */ }
    target.replaceChildren();
    if (!recent.length) {
      if (page === 'search') target.appendChild(el('span', 'muted', 'No searches yet.'));
      target.hidden = page === 'home';
    } else {
      target.hidden = false;
      recent.forEach(q => {
        const b = el('button', 'chip'); b.type = 'button';
        b.append(icon('clock'), el('span', '', q));
        b.addEventListener('click', () => onPick(q));
        target.appendChild(b);
      });
    }
    const clr = $('#clearHistory'); if (clr) clr.hidden = !recent.length;
  }

  /* ---------- viewer modal ---------- */
  const viewer = $('#viewer');
  let viewerId = null;
  async function loadViewer(q) {
    try {
      const d = await api('/api/documents/' + viewerId + '/text?q=' + encodeURIComponent(q || ''));
      $('#viewerTitle').textContent = d.filename;
      $('#viewerText').innerHTML = d.html + (d.truncated ? '\n\n… (showing the first 200,000 characters)' : '');   // html is escaped by the server
      $('#viewerCount').textContent = q ? d.matches + ' match' + (d.matches === 1 ? '' : 'es') : '';
    } catch (e) { toast(e.message, 'err'); closeViewer(); }
  }
  function openViewer(id, q) {
    viewerId = id; $('#viewerFind').value = q || ''; viewer.hidden = false; $('#viewerText').textContent = 'Loading…';
    loadViewer(q); $('#viewerClose').focus();
  }
  function closeViewer() { viewer.hidden = true; viewerId = null; }
  $('#viewerClose').addEventListener('click', closeViewer);
  viewer.addEventListener('click', e => { if (e.target === viewer) closeViewer(); });
  document.addEventListener('keydown', e => { if (e.key === 'Escape' && !viewer.hidden) closeViewer(); });
  $('#viewerFind').addEventListener('input', debounce(e => loadViewer(e.target.value), 200));

  /* ======================= HOME ======================= */
  function initHome() {
    initSearchBox();
    loadRecent($('#homeRecent'), q => { location.href = '/search?q=' + encodeURIComponent(q); });
    api('/api/index/status').then(s => {
      $('#homeStats').textContent = s.documents
        ? 'Your files stay on your device. ' + fmtNum(s.documents) + ' documents and ' + fmtNum(s.words) + ' words are ready to search.'
        : 'Your files stay on your device. Add documents to build your private library.';
    }).catch(() => {});
  }

  /* ======================= SEARCH ======================= */
  function initSearch() {
    const input = $('#q'), results = $('#results'), stats = $('#stats');
    const states = { idle: $('#stateIdle'), library: $('#stateLibrary'), none: $('#stateNone'), error: $('#stateError') };
    const F = { type: $('#fType'), date: $('#fDate'), rel: $('#fRel'), sort: $('#fSort') };
    let lastTerms = [];

    function show(which) { Object.entries(states).forEach(([k, n]) => n.hidden = k !== which); }
    function params(q) {
      const p = new URLSearchParams({ q: q });
      if (F.type.value !== 'all') p.set('type', F.type.value);
      if (F.date.value !== 'any') p.set('date', F.date.value);
      if (F.rel.value !== '0') p.set('rel', F.rel.value);
      if (F.sort.value !== 'relevance') p.set('sort', F.sort.value);
      return p;
    }
    function card(r) {
      const art = el('article', 'result');
      const head = el('div', 'r-head');
      const h = el('h3', 'r-title'); const b = el('button', '', r.filename); b.type = 'button'; b.title = 'View document';
      b.addEventListener('click', () => openViewer(r.id, input.value));
      h.appendChild(b);
      head.append(h, el('span', 'score', 'Relevance: ' + r.relevance + '%'));
      const meter = el('div', 'meter'); const bar = el('span'); bar.style.width = r.relevance + '%'; meter.appendChild(bar);
      const snip = el('p', 'snippet'); snip.innerHTML = r.snippet;        // server-escaped; only <mark> tags are added
      const meta = el('div', 'r-meta');
      const t = el('span'); t.append(icon('file'), el('span', 'type', r.ext.toUpperCase()));
      const p = el('span'); p.append(icon('folder'), document.createTextNode(r.path));
      const d = el('span'); d.append(icon('clock'), document.createTextNode('Modified ' + fmtDate(r.modified)));
      meta.append(t, p, d, el('span', '', fmtBytes(r.size)));
      art.append(head, meter, snip, meta);
      return art;
    }
    async function run(q, push) {
      q = (q || '').trim();
      input.value = q; $('#clearBtn').hidden = !q;
      results.replaceChildren(); stats.hidden = true;
      if (!q) { show('idle'); history.replaceState(null, '', '/search'); return; }
      if (push !== false) history.replaceState(null, '', '/search?q=' + encodeURIComponent(q));
      try {
        const d = await api('/api/search?' + params(q));
        lastTerms = d.terms;
        stats.hidden = false; stats.replaceChildren();
        const n = d.count, ms = d.time_ms;
        stats.append(el('b', '', fmtNum(n)), document.createTextNode(' result' + (n === 1 ? '' : 's') + ' found in '),
                     el('b', '', (ms < 10 ? ms.toFixed(1) : Math.round(ms)) + ' ms'));
        if (d.count > d.results.length) stats.append(document.createTextNode(' (showing the top ' + d.results.length + ')'));
        if (!d.results.length) show(d.library_size ? 'none' : 'library');
        else { show(''); d.results.forEach(r => results.appendChild(card(r))); }
      } catch (e) {
        stats.hidden = true; show('error'); states.error.textContent = e.message;
      }
      loadRecent($('#recent'), pick);
    }
    const pick = q => run(q);
    onSearch = q => run(q);
    initSearchBox();
    Object.values(F).forEach(s => s.addEventListener('change', () => { if (input.value.trim()) run(input.value); }));
    $('#clearHistory').addEventListener('click', async () => {
      try { await api('/api/recent', { method: 'DELETE' }); toast('Search history cleared.', 'ok'); loadRecent($('#recent'), pick); }
      catch (e) { toast(e.message, 'err'); }
    });
    loadRecent($('#recent'), pick);
    const p = new URLSearchParams(location.search);
    ['type', 'date', 'sort', 'rel'].forEach(k => { if (p.get(k) && F[k]) F[k].value = p.get(k); });
    if (p.get('q')) run(p.get('q'), false); else show('idle');
  }

  /* ======================= DOCUMENTS ======================= */
  function initDocuments() {
    let supported = ['.txt', '.md', '.html', '.csv'], maxMb = 10, docs = [];
    const drop = $('#drop'), input = $('#fileInput'), queue = $('#queue'), grid = $('#docs');
    const btns = ['#btnBuild', '#btnRebuild', '#btnClear'].map(s => $(s));

    async function refreshStatus() {
      try {
        const s = await api('/api/index/status');
        $('#stDocs').textContent = fmtNum(s.documents); $('#stWords').textContent = fmtNum(s.words);
        $('#stUpdate').textContent = fmtDate(s.last_update);
        $('#stState').textContent = s.status + (s.pending ? ' (' + s.pending + ' file' + (s.pending > 1 ? 's' : '') + ' waiting)' : '');
        const st = $('#idxStatus'); st.textContent = s.status; st.className = 'status ' + (s.status === 'Ready' ? 'ready' : 'warn');
        const sk = $('#skipped'); sk.replaceChildren();
        sk.hidden = !s.failed.length;
        if (s.failed.length) {
          sk.appendChild(document.createTextNode('Some files in data/documents could not be indexed:'));
          const ul = el('ul'); s.failed.forEach(f => ul.appendChild(el('li', '', f.file + ' — ' + f.error))); sk.appendChild(ul);
        }
      } catch (e) { toast(e.message, 'err'); }
    }
    function renderDocs() {
      const f = $('#libFilter').value.trim().toLowerCase();
      const shown = docs.filter(d => !f || d.filename.toLowerCase().includes(f) || d.rel.toLowerCase().includes(f));
      $('#libCount').textContent = docs.length;
      grid.replaceChildren();
      $('#docsEmpty').hidden = docs.length > 0;
      shown.forEach(d => {
        const c = el('article', 'doc');
        const top = el('div', 'doc-top'); const info = el('div');
        info.append(el('h3', '', d.filename), el('div', 'path', 'Documents/' + (d.rel.includes('/') ? d.rel.slice(0, d.rel.lastIndexOf('/')) : '')));
        top.append(el('div', 'ext', d.ext.slice(1)), info);
        const meta = el('div', 'doc-meta');
        meta.append(el('span', 'pill', '✓ Indexed'), el('span', '', fmtBytes(d.size)), el('span', '', fmtNum(d.words) + ' words'), el('span', '', 'Modified ' + fmtDate(d.modified)));
        const act = el('div', 'doc-actions');
        const view = el('button', 'btn ghost sm'); view.type = 'button'; view.append(icon('eye'), document.createTextNode('View'));
        view.addEventListener('click', () => openViewer(d.id, ''));
        const rm = el('button', 'btn ghost danger sm'); rm.type = 'button'; rm.append(icon('trash'), document.createTextNode('Remove'));
        rm.addEventListener('click', () => removeDoc(d));
        act.append(view, rm);
        c.append(top, meta, act); grid.appendChild(c);
      });
      if (docs.length && !shown.length) grid.appendChild(el('p', 'muted', 'No document names match your filter.'));
    }
    async function loadDocs() {
      try { docs = (await api('/api/documents')).documents; renderDocs(); } catch (e) { toast(e.message, 'err'); }
    }
    async function removeDoc(d) {
      if (!confirm('Remove "' + d.filename + '" from your library?\n\nThe copy in data/documents is deleted and the file leaves the index. Original files elsewhere on your computer are not touched.')) return;
      try { const r = await api('/api/documents/' + d.id, { method: 'DELETE' }); toast(r.message, 'ok'); await Promise.all([loadDocs(), refreshStatus()]); }
      catch (e) { toast(e.message, 'err'); }
    }
    async function indexAction(kind, label, confirmText) {
      if (confirmText && !confirm(confirmText)) return;
      btns.forEach(b => b.disabled = true);
      try { const r = await api('/api/index/' + kind, { method: 'POST' }); toast(r.message, 'ok'); }
      catch (e) { toast(e.message, 'err'); }
      btns.forEach(b => b.disabled = false);
      await Promise.all([loadDocs(), refreshStatus()]);
    }
    $('#btnBuild').addEventListener('click', () => indexAction('build'));
    $('#btnRebuild').addEventListener('click', () => indexAction('rebuild', '', 'Rebuild the whole index from the files in data/documents?'));
    $('#btnClear').addEventListener('click', () => indexAction('clear', '', 'Clear the search index?\n\nOnly the index is removed. Your documents stay in data/documents, and Build Index recreates it.'));
    $('#libFilter').addEventListener('input', renderDocs);

    /* upload */
    function uploadOne(file) {
      const li = el('li', 'q-item'), top = el('div', 'q-top'), name = el('span', 'q-name', file.name), msg = el('span', 'q-msg', 'Waiting…');
      const bar = el('div', 'q-bar'), fill = el('span'); bar.appendChild(fill); top.append(name, msg); li.append(top, bar); queue.prepend(li);
      const fail = text => { msg.textContent = text; msg.className = 'q-msg err'; fill.style.width = '100%'; fill.style.background = 'var(--danger)'; toast(text, 'err'); };
      const ext = '.' + (file.name.split('.').pop() || '').toLowerCase();
      if (!file.name.includes('.') || !supported.includes(ext)) { fail('“' + file.name + '” is not supported. Allowed: ' + supported.join(', ')); return Promise.resolve(false); }
      if (file.size === 0) { fail('“' + file.name + '” is empty.'); return Promise.resolve(false); }
      if (file.size > maxMb * 1048576) { fail('“' + file.name + '” is larger than ' + maxMb + ' MB.'); return Promise.resolve(false); }
      return new Promise(resolve => {
        const xhr = new XMLHttpRequest(), fd = new FormData(); fd.append('file', file);
        xhr.open('POST', '/api/upload');
        msg.textContent = 'Uploading…';
        xhr.upload.onprogress = e => { if (e.lengthComputable) fill.style.width = Math.round(e.loaded / e.total * 90) + '%'; };
        xhr.upload.onload = () => { msg.textContent = 'Indexing…'; fill.style.width = '95%'; };
        xhr.onerror = () => { fail('Cannot reach the local Privata server.'); resolve(false); };
        xhr.onload = () => {
          let d = null; try { d = JSON.parse(xhr.responseText); } catch (e) { /* ignore */ }
          if (xhr.status === 200 && d && d.ok) { fill.style.width = '100%'; msg.textContent = d.message; msg.className = 'q-msg ok'; resolve(true); }
          else { fail((d && d.error) || (xhr.status === 413 ? 'The file is too large.' : 'Upload failed.')); resolve(false); }
        };
        xhr.send(fd);
      });
    }
    async function handleFiles(files) {
      files = Array.from(files); if (!files.length) return;
      let okCount = 0;
      for (const f of files) { if (await uploadOne(f)) okCount++; }
      if (okCount) toast(okCount + ' document' + (okCount > 1 ? 's' : '') + ' indexed successfully.', 'ok');
      await Promise.all([loadDocs(), refreshStatus()]);
    }
    const pickFiles = () => input.click();
    $('#browse').addEventListener('click', e => { e.stopPropagation(); pickFiles(); });
    $('#emptyAdd').addEventListener('click', () => { drop.scrollIntoView({ behavior: 'smooth', block: 'center' }); pickFiles(); });
    drop.addEventListener('click', pickFiles);
    drop.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); pickFiles(); } });
    input.addEventListener('change', () => { handleFiles(input.files); input.value = ''; });
    ['dragenter', 'dragover'].forEach(ev => drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.add('over'); }));
    ['dragleave', 'drop'].forEach(ev => drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.remove('over'); }));
    drop.addEventListener('drop', e => handleFiles(e.dataTransfer.files));
    window.addEventListener('dragover', e => e.preventDefault());       // dropping outside the zone must not navigate away
    window.addEventListener('drop', e => e.preventDefault());

    api('/api/config').then(c => {
      supported = c.supported; maxMb = c.max_mb; input.accept = supported.join(',');
      $('#typesHint').textContent = 'Supported: ' + supported.join(' ') + ' · max ' + maxMb + ' MB each';
    }).catch(() => {});
    loadDocs(); refreshStatus();
    if (location.hash === '#upload') setTimeout(() => $('#upload').scrollIntoView({ behavior: 'smooth' }), 150);
  }

  /* ======================= ANALYTICS ======================= */
  function bars(target, rows, labelKey, valueKey, emptyText) {
    target.replaceChildren();
    if (!rows.length) { target.appendChild(el('p', 'muted', emptyText)); return; }
    const max = Math.max(...rows.map(r => r[valueKey])) || 1;
    rows.forEach(r => {
      const row = el('div', 'hbar'), track = el('div', 'track'), fill = el('div', 'fill');
      row.append(el('span', 't', r[labelKey]), track, el('span', 'n', r[valueKey]));
      track.appendChild(fill); target.appendChild(row);
      requestAnimationFrame(() => { fill.style.width = Math.max(4, r[valueKey] / max * 100) + '%'; });
    });
  }
  async function initAnalytics() {
    try {
      const a = await api('/api/analytics');
      $('#aDocs').textContent = fmtNum(a.documents); $('#aWords').textContent = fmtNum(a.words);
      $('#aSearches').textContent = fmtNum(a.total_searches);
      $('#aAvg').textContent = a.total_searches ? a.avg_ms + ' ms' : '–';
      $('#aTerms').textContent = fmtNum(a.terms); $('#aNone').textContent = fmtNum(a.no_results);
      bars($('#cTerms'), a.top_terms, 'term', 'count', 'No searches yet. Try the Search page.');
      bars($('#cTypes'), a.types.map(t => ({ type: t.type.toUpperCase(), docs: t.docs })), 'type', 'docs', 'No documents indexed yet.');
      const days = $('#cDays'); days.replaceChildren();
      const max = Math.max(1, ...a.per_day.map(d => d.count));
      a.per_day.forEach(d => {
        const v = el('div', 'vbar'), col = el('div', 'col');
        v.append(el('span', '', d.count), col, el('span', '', d.label)); days.appendChild(v);
        requestAnimationFrame(() => { col.style.height = (d.count / max * 80) + '%'; });
      });
    } catch (e) { toast(e.message, 'err'); }
  }

  /* ---------- start ---------- */
  if (page === 'home') initHome();
  else if (page === 'search') initSearch();
  else if (page === 'documents') initDocuments();
  else if (page === 'analytics') initAnalytics();
})();
