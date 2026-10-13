(() => {
  const CFG = window.STAR_CFG || {};
  const REPO = CFG.repo || '', OWNER = REPO.split('/')[0].toLowerCase();
  const KEY = 'ghStarToken';
  const ID_RE = /item:\s*(\d{4}-\d{2}-\d{2}#\d+)/;
  let stars = {...(CFG.initial || {})};          // id -> {number, note}
  const listeners = [];

  const css = document.createElement('style');
  css.textContent = `
  [data-star]{cursor:pointer}
  .star-toast{position:fixed;left:50%;bottom:24px;transform:translateX(-50%);background:var(--ink,#1d1d1b);color:var(--card,#fff);
    padding:10px 16px;border-radius:999px;font:600 14px/1.2 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;
    z-index:100;box-shadow:0 4px 18px rgba(0,0,0,.25);opacity:0;transition:opacity .2s;pointer-events:none;max-width:90vw;text-align:center}
  .star-toast.show{opacity:1}
  .star-modal{position:fixed;inset:0;background:rgba(0,0,0,.45);z-index:90;display:flex;align-items:center;justify-content:center;padding:16px}
  .star-modal .box{background:var(--card,#fff);color:var(--ink,#1d1d1b);border-radius:12px;max-width:480px;width:100%;padding:22px 22px 18px;
    font:14px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;box-shadow:0 10px 40px rgba(0,0,0,.3)}
  .star-modal h2{margin:0 0 8px;font-size:18px}
  .star-modal ol{padding-left:20px;margin:10px 0}
  .star-modal li{margin:4px 0}
  .star-modal a{color:var(--accent,#1f6f5c)}
  .star-modal input{width:100%;padding:9px 11px;border:1px solid var(--line,#dcdad3);border-radius:8px;background:var(--bg,#f4f3ef);color:inherit;font:inherit;margin:6px 0 12px}
  .star-modal .btns{display:flex;gap:8px;justify-content:flex-end}
  .star-modal button{border:1px solid var(--line,#dcdad3);background:none;color:inherit;border-radius:8px;padding:7px 14px;font:inherit;cursor:pointer}
  .star-modal button.primary{background:var(--ink,#1d1d1b);color:var(--card,#fff);border-color:transparent}
  .star-modal .muted{color:var(--muted,#6b6a65);font-size:12px}`;
  document.head.appendChild(css);

  const token = () => { try { return localStorage.getItem(KEY) || ''; } catch (e) { return ''; } };
  const api = (path, opts = {}) => fetch(`https://api.github.com/repos/${REPO}${path}`, {
    ...opts,
    headers: {Accept: 'application/vnd.github+json', ...(token() ? {Authorization: `Bearer ${token()}`} : {}),
              ...(opts.body ? {'Content-Type': 'application/json'} : {})},
  });
  const noteOf = body => (body || '').replace(ID_RE, '').replace(/<!--[\s\S]*?-->/g, '').trim();

  function toast(msg) {
    let t = document.querySelector('.star-toast');
    if (!t) { t = document.createElement('div'); t.className = 'star-toast'; document.body.appendChild(t); }
    t.textContent = msg; t.classList.add('show');
    clearTimeout(t._h); t._h = setTimeout(() => t.classList.remove('show'), 2400);
  }

  function paint() {
    document.querySelectorAll('[data-star]').forEach(el => {
      const s = stars[el.dataset.star], on = !!s;
      el.classList.toggle('on', on);
      el.textContent = el.dataset.style === 'label' ? (on ? '★ Starred' : '☆ Star') : (on ? '★' : '☆');
      el.title = on ? 'Starred: click to un-star' : 'Star this story';
      el.setAttribute('aria-pressed', on ? 'true' : 'false');
      el.setAttribute('role', 'button');
    });
  }
  function emit() { paint(); listeners.forEach(f => f()); }

  async function load() {
    if (!REPO) return;
    try {
      const out = {};
      for (let page = 1; page <= 10; page++) {
        const r = await api(`/issues?labels=star&state=open&per_page=100&page=${page}`, {cache: 'no-store'});
        if (!r.ok) throw new Error(r.status);
        const batch = await r.json();
        batch.forEach(i => {
          const m = ID_RE.exec(i.body || '');
          if (m && (i.user?.login || '').toLowerCase() === OWNER) out[m[1]] = {number: i.number, note: noteOf(i.body)};
        });
        if (batch.length < 100) break;
      }
      stars = out; emit();
    } catch (e) { /* offline or rate-limited: keep the stars baked in at build time */ }
  }

  async function fail(r, what) {
    if (r.status === 401) { forget(); toast('GitHub token expired or invalid. Connect again.'); return connect(); }
    if (r.status === 403 || r.status === 404) return toast(`Couldn't ${what}: the token needs Issues read & write on ${REPO}.`);
    toast(`Couldn't ${what} (GitHub error ${r.status}).`);
  }

  const busy = new Set();
  async function toggle(id) {
    if (!token()) return connect(() => toggle(id));
    if (busy.has(id)) return;
    busy.add(id);
    try {
      const cur = stars[id];
      if (cur) {
        delete stars[id]; emit();
        const r = await api(`/issues/${cur.number}`, {method: 'PATCH', body: JSON.stringify({state: 'closed', state_reason: 'not_planned'})});
        if (!r.ok) { stars[id] = cur; emit(); return fail(r, 'un-star'); }
        toast('Un-starred');
      } else {
        stars[id] = {number: null, note: ''}; emit();
        const headline = (CFG.headlines || {})[id] || id;
        const r = await api('/issues', {method: 'POST', body: JSON.stringify({title: `★ ${headline}`.slice(0, 200), body: `item: ${id}\n`, labels: ['star']})});
        if (!r.ok) { delete stars[id]; emit(); return fail(r, 'star'); }
        stars[id] = {number: (await r.json()).number, note: ''}; emit();
        toast('Starred ★');
      }
    } finally { busy.delete(id); }
  }

  async function setNote(id, note) {
    const cur = stars[id];
    if (!cur?.number) return;
    if (!token()) return connect(() => setNote(id, note));
    const r = await api(`/issues/${cur.number}`, {method: 'PATCH', body: JSON.stringify({body: `item: ${id}\n\n${note}`})});
    if (!r.ok) return fail(r, 'save the note');
    stars[id] = {...cur, note}; emit(); toast('Note saved');
  }

  function forget() { try { localStorage.removeItem(KEY); } catch (e) {} emit(); }

  function connect(after) {
    if (document.querySelector('.star-modal')) return;
    const owner = REPO.split('/')[0], name = REPO.split('/')[1];
    const url = 'https://github.com/settings/personal-access-tokens/new?' + new URLSearchParams({
      name: 'Daily Clippings stars', description: `Star stories on the ${name} archive`,
      target_name: owner, expires_in: 'none', issues: 'write'});
    const m = document.createElement('div');
    m.className = 'star-modal';
    m.innerHTML = `<div class="box" role="dialog" aria-modal="true" aria-label="Connect GitHub">
      <h2>Connect GitHub to star with one click</h2>
      <div>Stars are saved as issues in <b>${REPO}</b>, so this browser needs a GitHub token once.</div>
      <ol>
        <li><a href="${url}" target="_blank" rel="noopener">Create a fine-grained token ↗</a></li>
        <li>Repository access: <b>Only select repositories</b> → <b>${name}</b></li>
        <li>Permissions → Repository → <b>Issues: Read and write</b> (it may already be set)</li>
        <li>Generate, copy, and paste it here:</li>
      </ol>
      <input type="password" placeholder="github_pat_…" autocomplete="off" spellcheck="false">
      <div class="muted" style="margin:-6px 0 12px">The token stays only in this browser (localStorage) and is sent only to api.github.com.</div>
      <div class="btns"><button type="button" data-act="cancel">Cancel</button><button type="button" class="primary" data-act="save">Save</button></div></div>`;
    document.body.appendChild(m);
    const input = m.querySelector('input');
    input.focus();
    const close = () => m.remove();
    m.addEventListener('click', async e => {
      if (e.target === m || e.target.dataset.act === 'cancel') return close();
      if (e.target.dataset.act !== 'save') return;
      const t = input.value.trim();
      if (!t) return input.focus();
      try { localStorage.setItem(KEY, t); } catch (err) { return toast('This browser blocks storage; stars cannot be saved here.'); }
      const r = await api('/issues?labels=star&per_page=1');
      if (!r.ok) { forget(); return toast('That token was not accepted by GitHub.'); }
      close(); toast('GitHub connected'); emit();
      if (after) after();
    });
    input.addEventListener('keydown', e => { if (e.key === 'Enter') m.querySelector('[data-act=save]').click(); if (e.key === 'Escape') close(); });
  }

  document.addEventListener('click', e => {
    const el = e.target.closest('[data-star]');
    if (!el) return;
    e.preventDefault(); e.stopPropagation();
    toggle(el.dataset.star);
  }, true);

  window.Stars = {
    isStarred: id => !!stars[id], note: id => stars[id]?.note || '', all: () => Object.keys(stars),
    connected: () => !!token(), connect, disconnect: () => { forget(); toast('GitHub disconnected'); },
    toggle, setNote, onChange: f => listeners.push(f), paint,
  };

  // links from the email: ...#star=2026-10-13%231 → star it here
  const want = new URLSearchParams(location.hash.slice(1)).get('star');
  paint();
  load().then(() => {
    if (!want) return;
    const p = new URLSearchParams(location.hash.slice(1)); p.delete('star');
    history.replaceState(null, '', p.toString() ? '#' + p : location.pathname);
    if (stars[want]) toast('Already starred ★'); else toggle(want);
  });
})();
