// ── DOM helper ────────────────────────────────────────────────────────────────
function h(tag, props, ...children) {
  const el = document.createElement(tag);
  if (props) {
    Object.entries(props).forEach(([k, v]) => {
      if (v == null) return;
      if (k === 'cls')     { el.className = v; }
      else if (k === 'style')   { el.style.cssText = v; }
      else if (k === 'text')    { el.textContent = v; }
      else if (k === 'onclick') { el.addEventListener('click', v); }
      else                      { el.setAttribute(k, v); }
    });
  }
  children.flat().forEach(c => {
    if (c == null) return;
    el.appendChild(c instanceof Node ? c : document.createTextNode(String(c)));
  });
  return el;
}

function icon(cls) {
  const i = document.createElement('i');
  i.className = cls;
  return i;
}

// ── State ─────────────────────────────────────────────────────────────────────
const App = {
  series: [],
  total: 0,
  page: 1,
  activeStatuses: new Set(['new', 'draft', 'approved', 'scheduled', 'posted']),
  currentSeriesId: null,
  currentSeries: null,
};

// ── API ───────────────────────────────────────────────────────────────────────
async function apiFetch(method, path, body) {
  const opts = { method };
  if (body instanceof FormData) {
    opts.body = body;
  } else if (body != null) {
    opts.headers = { 'Content-Type': 'application/json' };
    opts.body = JSON.stringify(body);
  }
  const resp = await fetch(path, opts);
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(err.detail || resp.statusText);
  }
  return resp.json();
}

// ── Toast ─────────────────────────────────────────────────────────────────────
function showToast(msg, type) {
  const cls = { success: 'text-bg-success', danger: 'text-bg-danger' }[type] || 'text-bg-secondary';
  const wrap = h('div', { cls: 'toast ' + cls, role: 'alert' });
  const inner = h('div', { cls: 'd-flex' });
  const body = h('div', { cls: 'toast-body', text: msg });
  const close = h('button', { cls: 'btn-close btn-close-white me-2 m-auto', type: 'button' });
  close.setAttribute('data-bs-dismiss', 'toast');
  inner.append(body, close);
  wrap.appendChild(inner);
  document.getElementById('toastContainer').appendChild(wrap);
  const t = new bootstrap.Toast(wrap, { delay: 3500 });
  t.show();
  wrap.addEventListener('hidden.bs.toast', () => wrap.remove());
}

// ── Confirm ───────────────────────────────────────────────────────────────────
function showConfirm(message, onOk) {
  document.getElementById('confirmBody').textContent = message;
  const old = document.getElementById('confirmOkBtn');
  const btn = old.cloneNode(true);
  old.replaceWith(btn);
  btn.id = 'confirmOkBtn';
  btn.addEventListener('click', onOk);
  bootstrap.Modal.getOrCreateInstance(document.getElementById('confirmModal')).show();
}

// ── Utilities ─────────────────────────────────────────────────────────────────
function formatDate(isoStr) {
  if (!isoStr) return '';
  const d = new Date(isoStr.endsWith('Z') ? isoStr : isoStr + 'Z');
  return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' }) + ' ' +
         d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
}

const STATUS_COLOR = {
  new: 'bg-info text-dark', draft: 'bg-warning text-dark',
  approved: 'bg-primary', scheduled: 'bg-purple',
  posted: 'bg-success', skip: 'bg-secondary',
};

function statusBadge(status, needsReview) {
  const frag = document.createDocumentFragment();
  frag.appendChild(h('span', { cls: 'badge ' + (STATUS_COLOR[status] || 'bg-secondary'), text: status }));
  if (needsReview) frag.appendChild(h('span', { cls: 'badge bg-danger ms-1', text: '⚠' }));
  return frag;
}

// ── Series list ───────────────────────────────────────────────────────────────
async function loadSeries(reset) {
  if (reset) {
    App.page = 1; App.series = [];
    document.getElementById('seriesItems').replaceChildren();
  }
  document.getElementById('seriesListLoading').classList.remove('d-none');
  try {
    const statuses = [...App.activeStatuses].join(',') || 'new';
    const q = new URLSearchParams({ page: App.page, limit: 20, status: statuses });
    const data = await apiFetch('GET', '/api/series?' + q);
    App.series.push(...data.items);
    App.total = data.total;
    const container = document.getElementById('seriesItems');
    data.items.forEach(s => container.appendChild(buildSeriesItem(s)));
    document.getElementById('loadMoreBtn').classList.toggle('d-none', App.series.length >= App.total);
  } catch (e) {
    showToast(e.message, 'danger');
  } finally {
    document.getElementById('seriesListLoading').classList.add('d-none');
  }
}

async function loadMoreSeries() {
  App.page++;
  await loadSeries(false);
}

function buildSeriesItem(s) {
  const name = s.title || s.original_folder_name || s.id.slice(0, 8);
  let cover;
  if (s.cover_url) {
    cover = document.createElement('img');
    cover.setAttribute('src', s.cover_url);
    cover.className = 'rounded flex-shrink-0';
    cover.style.cssText = 'width:48px;height:40px;object-fit:cover';
    cover.loading = 'lazy';
  } else {
    const imgIcon = icon('bi bi-image text-muted');
    imgIcon.style.fontSize = '14px';
    cover = h('div', {
      cls: 'rounded flex-shrink-0 bg-secondary d-flex align-items-center justify-content-center',
      style: 'width:48px;height:40px',
    }, imgIcon);
  }

  const nameEl = h('div', { cls: 'text-truncate', style: 'font-size:13px;font-weight:500', text: name });
  const badgesRow = h('div', { cls: 'd-flex gap-1 align-items-center flex-wrap' });
  badgesRow.appendChild(statusBadge(s.status, s.needs_review));
  badgesRow.appendChild(h('span', { cls: 'text-muted', style: 'font-size:11px', text: s.image_count + ' img' }));
  const info = h('div', { cls: 'flex-grow-1 overflow-hidden' }, nameEl, badgesRow);

  if (s.scheduled_at) {
    const sched = h('div', { cls: 'text-purple', style: 'font-size:11px' });
    sched.appendChild(icon('bi bi-clock me-1'));
    sched.appendChild(document.createTextNode(formatDate(s.scheduled_at)));
    info.appendChild(sched);
  }

  return h('div', {
    cls: 'series-item d-flex align-items-start gap-2 p-2 border-bottom' +
         (App.currentSeriesId === s.id ? ' bg-body-secondary' : ''),
    id: 'si-' + s.id,
    'data-id': s.id,
    onclick: () => selectSeries(s.id),
  }, cover, info);
}

function updateSeriesItem(s) {
  const old = document.getElementById('si-' + s.id);
  if (old) old.replaceWith(buildSeriesItem(s));
}

async function selectSeries(id) {
  App.currentSeriesId = id;
  document.querySelectorAll('.series-item').forEach(el => {
    el.classList.toggle('bg-body-secondary', el.dataset.id === id);
  });
  showView('editor');
  await loadSeriesDetail(id);
}

async function loadSeriesDetail(id) {
  const panel = document.getElementById('editorPanel');
  panel.replaceChildren(h('div', { cls: 'text-center p-5' }, h('div', { cls: 'spinner-border text-secondary' })));
  try {
    const s = await apiFetch('GET', '/api/series/' + id);
    App.currentSeries = s;
    renderEditor(s);
  } catch (e) {
    panel.replaceChildren(h('div', { cls: 'alert alert-danger', text: e.message }));
  }
}

async function createSeries() {
  try {
    const s = await apiFetch('POST', '/api/series', { title: '' });
    document.getElementById('seriesItems').prepend(buildSeriesItem(s));
    App.series.unshift(s);
    await selectSeries(s.id);
  } catch (e) {
    showToast(e.message, 'danger');
  }
}

// ── Filter ────────────────────────────────────────────────────────────────────
function onFilterChange() {
  App.activeStatuses = new Set(
    [...document.querySelectorAll('#statusFilterMenu input:checked')].map(el => el.value)
  );
  loadSeries(true);
}

// ── View switching ────────────────────────────────────────────────────────────
function showView(view) {
  const sidebar = document.getElementById('seriesSidebar');
  const editor  = document.getElementById('editorPanel');
  const queue   = document.getElementById('queuePanel');
  const back    = document.getElementById('backBtnRow');
  const mobile  = window.innerWidth < 992;

  if (!mobile) {
    sidebar.classList.remove('d-none');
    back.classList.add('d-none');
    editor.classList.toggle('d-none', view === 'queue');
    queue.classList.toggle('d-none',  view !== 'queue');
  } else if (view === 'list') {
    sidebar.classList.remove('d-none');
    editor.classList.add('d-none');
    queue.classList.add('d-none');
    back.classList.add('d-none');
  } else {
    sidebar.classList.add('d-none');
    back.classList.remove('d-none');
    editor.classList.toggle('d-none', view !== 'editor');
    queue.classList.toggle('d-none',  view !== 'queue');
  }
  if (view === 'queue') refreshQueue();
}

// ── Queue ─────────────────────────────────────────────────────────────────────
async function refreshQueue() {
  const el = document.getElementById('queueContent');
  el.replaceChildren(h('div', { cls: 'text-center' }, h('div', { cls: 'spinner-border spinner-border-sm' })));
  try {
    const items = await apiFetch('GET', '/api/queue');
    if (!items.length) {
      el.replaceChildren(h('p', { cls: 'text-muted', text: 'No scheduled posts.' }));
      return;
    }
    const tbody = document.createElement('tbody');
    items.forEach(item => {
      const targetsCell = document.createElement('td');
      item.targets.forEach(t => targetsCell.appendChild(h('span', { cls: 'badge bg-secondary me-1', text: t })));
      const edit   = h('button', { cls: 'btn btn-xs btn-outline-secondary me-1', text: 'Edit',   onclick: () => selectSeries(item.series_id) });
      const cancel = h('button', { cls: 'btn btn-xs btn-outline-danger',          text: 'Cancel', onclick: () => cancelScheduleItem(item.series_id) });
      tbody.appendChild(h('tr', null,
        h('td', { text: item.title || item.original_folder_name || item.series_id.slice(0, 8) }),
        h('td', { text: formatDate(item.scheduled_at) }),
        targetsCell,
        h('td', null, edit, cancel)));
    });
    el.replaceChildren(h('div', { cls: 'table-responsive' },
      h('table', { cls: 'table table-sm table-hover align-middle' },
        h('thead', null, h('tr', null,
          h('th', { text: 'Series' }), h('th', { text: 'Datetime (UTC)' }),
          h('th', { text: 'Platforms' }), h('th'))),
        tbody)));
  } catch (e) {
    el.replaceChildren(h('div', { cls: 'alert alert-danger', text: e.message }));
  }
}

async function cancelScheduleItem(seriesId) {
  showConfirm('Cancel this scheduled post?', async () => {
    try {
      await apiFetch('DELETE', '/api/series/' + seriesId + '/schedule');
      showToast('Schedule cancelled', 'success');
      await refreshQueue();
      const s = await apiFetch('GET', '/api/series/' + seriesId);
      updateSeriesItem(s);
    } catch (e) { showToast(e.message, 'danger'); }
  });
}

// ── Draft helpers ─────────────────────────────────────────────────────────────
function getDraftEdits() {
  return {
    title:   document.getElementById('f_title')?.value,
    desc_en: document.getElementById('f_desc_en')?.value,
    desc_ru: document.getElementById('f_desc_ru')?.value,
    tags_ig: document.getElementById('f_tags_ig')?.value,
    tags_tg: document.getElementById('f_tags_tg')?.value,
  };
}

// ── Init ──────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  loadSeries(true);
  initLightbox();
  setInterval(() => {
    if (!App.currentSeriesId) return;
    const d = getDraftEdits();
    if (d.desc_en || d.desc_ru || d.title)
      localStorage.setItem('draft_' + App.currentSeriesId, JSON.stringify(d));
  }, 30000);
  window.addEventListener('resize', () => {
    if (window.innerWidth >= 992) {
      document.getElementById('seriesSidebar').classList.remove('d-none');
      document.getElementById('backBtnRow').classList.add('d-none');
    }
  });
});
