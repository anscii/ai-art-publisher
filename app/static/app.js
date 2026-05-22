// ── AI provider model catalogue (fetched from /api/settings/providers) ────────
let PROVIDER_MODELS = {};

function buildProviderModelSelect(selectEl, provider, { withDefault = false, selectedValue = '' } = {}) {
  const models = PROVIDER_MODELS[provider] || [];
  selectEl.replaceChildren();
  if (withDefault) {
    const o = document.createElement('option'); o.value = ''; o.textContent = 'Default'; selectEl.appendChild(o);
  }
  models.forEach(({ id, label }) => {
    const o = document.createElement('option'); o.value = id; o.textContent = label;
    if (id === selectedValue) o.selected = true;
    selectEl.appendChild(o);
  });
  if (!withDefault && !selectedValue && models.length) selectEl.value = models[0].id;
}

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
  limit: 15,
  activeStatuses: new Set(['new', 'draft', 'approved']),
  collections: [],
  activeCollection: null,
  currentSeriesId: null,
  currentSeries: null,
  unsortedSeriesId: null,
  search: '',
  currentView: 'editor',
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
    const detail = err.detail;
    const msg = Array.isArray(detail)
      ? detail.map(d => d.msg || JSON.stringify(d)).join('; ')
      : (detail || resp.statusText);
    throw new Error(msg);
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
  const t = new bootstrap.Toast(wrap, type === 'danger' ? { autohide: false } : { delay: 3500 });
  t.show();
  wrap.addEventListener('hidden.bs.toast', () => wrap.remove());
}

// ── Error Service ─────────────────────────────────────────────────────────────
const ErrorService = (() => {
  const _log = [];
  const MAX = 20;
  const _listeners = new Set();
  const _cleared = new Set();

  function record(context, message) {
    _cleared.delete(context);
    const msg = message || 'Unknown error';
    _log.unshift({ ts: new Date(), context, message: msg });
    if (_log.length > MAX) _log.pop();
    showToast(msg, 'danger');
    _listeners.forEach(fn => fn());
  }

  function clear(context) {
    _cleared.add(context);
    _listeners.forEach(fn => fn());
  }

  function isCleared(context) { return _cleared.has(context); }
  function getAll() { return [..._log]; }
  function subscribe(fn) { _listeners.add(fn); return () => _listeners.delete(fn); }

  return { record, clear, isCleared, getAll, subscribe };
})();

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

function statusBadge(status) {
  const frag = document.createDocumentFragment();
  frag.appendChild(h('span', { cls: 'badge ' + (STATUS_COLOR[status] || 'bg-secondary'), text: status }));
  return frag;
}

// ── Series list ───────────────────────────────────────────────────────────────
let _sentinel = null;
let _observer = null;

function _updateSentinel(active) {
  if (!_sentinel) {
    _sentinel = h('div', { id: 'scrollSentinel', style: 'height:1px' });
    const sidebar = document.getElementById('seriesSidebar');
    sidebar.insertBefore(_sentinel, document.getElementById('loadMoreBtn'));
    _observer = new IntersectionObserver(entries => {
      if (entries[0].isIntersecting && App.series.length < App.total) {
        loadMoreSeries();
      }
    }, { threshold: 0.1 });
  }
  if (active) _observer.observe(_sentinel);
  else _observer.unobserve(_sentinel);
}

function _trimDomIfNeeded(container) {
  const items = container.querySelectorAll('[data-id]');
  if (items.length <= 100) return;
  for (let i = 0; i < 50; i++) items[i].remove();
  if (!document.getElementById('seriesTrimNotice')) {
    const notice = h('div', {
      id: 'seriesTrimNotice',
      cls: 'text-muted small text-center py-1 border-bottom',
      text: '↑ Scroll to top to reload from beginning',
    });
    container.prepend(notice);
  }
}

async function loadSeries(reset) {
  if (reset) {
    App.page = 1; App.series = [];
    document.getElementById('seriesItems').replaceChildren();
    document.getElementById('seriesTrimNotice')?.remove();
    if (_sentinel) _observer.unobserve(_sentinel);
  }
  document.getElementById('seriesListLoading').classList.remove('d-none');
  try {
    const statuses = [...App.activeStatuses].join(',') || 'new';
    const q = new URLSearchParams({ page: App.page, limit: App.limit, status: statuses });
    if (App.search) q.set('search', App.search);
    if (App.activeCollection) q.set('collection_id', App.activeCollection);
    const data = await apiFetch('GET', '/api/series?' + q);
    App.series.push(...data.items);
    App.total = data.total;
    const container = document.getElementById('seriesItems');
    const visible = data.items.filter(s => (s.name || s.title) !== 'Unsorted' && s.id !== App.unsortedSeriesId);
    visible.forEach(s => container.appendChild(buildSeriesItem(s)));
    const hasMore = App.series.length < App.total;
    document.getElementById('loadMoreBtn').classList.toggle('d-none', !hasMore);
    _updateSentinel(hasMore);
    if (!reset) _trimDomIfNeeded(container);
    if (reset && !App.currentSeriesId && visible.length > 0) {
      if (window.innerWidth >= 992) {
        selectSeries(visible[0].id, { push: false });
      } else {
        showView('list', { push: false });
      }
    }
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
  const name = s.name || s.title || s.original_folder_name || s.id.slice(0, 8);
  let cover;
  if (s.cover_url) {
    cover = document.createElement('img');
    cover.setAttribute('src', s.cover_url);
    cover.setAttribute('width', '48');
    cover.setAttribute('height', '40');
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
  badgesRow.appendChild(statusBadge(s.status));
  if (s.collection_name) {
    const cn = s.collection_name.length > 20 ? s.collection_name.slice(0, 19) + '…' : s.collection_name;
    const tooltip = s.collection_name_ru ? s.collection_name + ' / ' + s.collection_name_ru : s.collection_name;
    badgesRow.appendChild(h('span', { cls: 'badge bg-purple', style: 'font-size:10px', text: cn, title: tooltip }));
  }
  badgesRow.appendChild(h('span', { cls: 'text-muted', style: 'font-size:11px', text: s.image_count + ' img' }));
  const info = h('div', { cls: 'flex-grow-1 overflow-hidden' }, nameEl, badgesRow);

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
  if (!old) return;
  // SeriesDetail lacks cover_url / image_count — derive them from images[] when present
  const item = ('cover_url' in s) ? s : {
    ...s,
    cover_url: s.images?.find(i => !i.deleted_at)?.public_url ?? null,
    image_count: s.images?.filter(i => !i.deleted_at).length ?? 0,
    collection_name: s.collection?.name ?? null,
    collection_name_ru: s.collection?.name_ru ?? null,
  };
  old.replaceWith(buildSeriesItem(item));
}

async function selectSeries(id, { push = true } = {}) {
  App.currentSeriesId = id;
  document.querySelectorAll('.series-item').forEach(el => {
    el.classList.toggle('bg-body-secondary', el.dataset.id === id);
  });
  showView('editor', { push: false });
  await loadSeriesDetail(id);
  if (push) _pushState();
}

let _loadDetailToken = 0;

async function loadSeriesDetail(id) {
  const token = ++_loadDetailToken;
  const panel = document.getElementById('editorPanel');
  panel.replaceChildren(h('div', { cls: 'text-center p-5' }, h('div', { cls: 'spinner-border text-secondary' })));
  try {
    const s = await apiFetch('GET', '/api/series/' + id);
    if (token !== _loadDetailToken) return;
    App.currentSeries = s;
    renderEditor(s);
  } catch (e) {
    if (token !== _loadDetailToken) return;
    panel.replaceChildren(h('div', { cls: 'alert alert-danger', text: e.message }));
  }
}

async function selectUnsorted() {
  try {
    const s = await apiFetch('GET', '/api/series/unsorted');
    App.unsortedSeriesId = s.id;
    if (!App.series.find(x => x.id === s.id)) App.series.unshift(s);
    await selectSeries(s.id);
  } catch (e) { showToast(e.message, 'danger'); }
}

async function createSeries() {
  try {
    const s = await apiFetch('POST', '/api/series', { name: '', title: '' });
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
  _pushState();
}

let _searchDebounce = null;
function onSearchChange(val) {
  clearTimeout(_searchDebounce);
  _searchDebounce = setTimeout(() => {
    App.search = val.trim();
    loadSeries(true);
    _pushState();
  }, 300);
}

// ── View switching ────────────────────────────────────────────────────────────
function showView(view, { push = true } = {}) {
  App.currentView = view;
  const sidebar     = document.getElementById('seriesSidebar');
  const editor      = document.getElementById('editorPanel');
  const queue       = document.getElementById('queuePanel');
  const trash       = document.getElementById('trashPanel');
  const collections = document.getElementById('collectionsPanel');
  const stats       = document.getElementById('statsPanel');
  const back        = document.getElementById('backBtnRow');
  const mobile      = window.innerWidth < 992;
  const panels      = [editor, queue, trash, collections, stats];

  if (!mobile) {
    sidebar.classList.remove('d-none');
    back.classList.add('d-none');
    editor.classList.toggle('d-none', view !== 'editor' && view !== 'list');
    queue.classList.toggle('d-none',  view !== 'queue');
    trash.classList.toggle('d-none',  view !== 'trash');
    if (collections) collections.classList.toggle('d-none', view !== 'collections');
    if (stats) stats.classList.toggle('d-none', view !== 'stats');
  } else if (view === 'list') {
    sidebar.classList.remove('d-none');
    panels.forEach(p => p?.classList.add('d-none'));
    back.classList.add('d-none');
  } else {
    sidebar.classList.add('d-none');
    back.classList.remove('d-none');
    editor.classList.toggle('d-none', view !== 'editor');
    queue.classList.toggle('d-none',  view !== 'queue');
    trash.classList.toggle('d-none',  view !== 'trash');
    if (collections) collections.classList.toggle('d-none', view !== 'collections');
    if (stats) stats.classList.toggle('d-none', view !== 'stats');
  }
  if (view === 'queue') refreshQueue();
  if (view === 'trash') refreshTrash();
  if (view === 'collections') refreshCollections();
  if (view === 'stats') refreshStats();
  if (view !== 'editor' && view !== 'list') {
    App.activeCollection = null;
    const wrap = document.getElementById('collectionFilterWrap');
    _populateCollectionFilter();
  }
  if (push) _pushState();
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
      const platformCell = h('td', null, h('span', { cls: 'badge bg-secondary', text: item.platform }));
      const edit   = h('button', { cls: 'btn btn-xs btn-outline-secondary me-1', text: 'Edit',   onclick: () => selectSeries(item.series_id) });
      const cancel = h('button', { cls: 'btn btn-xs btn-outline-danger', text: 'Cancel', onclick: () => cancelPostScheduleItem(item.post_id) });
      tbody.appendChild(h('tr', null,
        h('td', { text: item.series_name || item.series_id.slice(0, 8) }),
        h('td', { text: item.title }),
        h('td', { text: formatDate(item.scheduled_at) }),
        platformCell,
        h('td', null, edit, cancel)));
    });
    el.replaceChildren(h('div', { cls: 'table-responsive' },
      h('table', { cls: 'table table-sm table-hover align-middle' },
        h('thead', null, h('tr', null,
          h('th', { text: 'Series' }), h('th', { text: 'Title' }),
          h('th', { text: 'Datetime (UTC)' }), h('th', { text: 'Platform' }), h('th'))),
        tbody)));
  } catch (e) {
    el.replaceChildren(h('div', { cls: 'alert alert-danger', text: e.message }));
  }
}

async function cancelPostScheduleItem(postId) {
  showConfirm('Cancel this scheduled post?', async () => {
    try {
      await apiFetch('DELETE', '/api/posts/' + postId + '/schedule');
      showToast('Schedule cancelled', 'success');
      await refreshQueue();
    } catch (e) { showToast(e.message, 'danger'); }
  });
}

// ── Collections ───────────────────────────────────────────────────────────────
async function refreshCollections() {
  const el = document.getElementById('collectionsContent');
  if (!el) return;
  el.replaceChildren(h('div', { cls: 'text-center' }, h('div', { cls: 'spinner-border spinner-border-sm' })));
  try {
    App.collections = await apiFetch('GET', '/api/collections');
    _populateCollectionFilter();
    if (!App.collections.length) {
      el.replaceChildren(h('p', { cls: 'text-muted', text: 'No collections yet.' }));
      return;
    }
    const list = h('div', { cls: 'd-flex flex-column gap-2' });
    App.collections.forEach(c => list.appendChild(_buildCollectionItem(c)));
    el.replaceChildren(list);
  } catch (e) {
    el.replaceChildren(h('div', { cls: 'alert alert-danger', text: e.message }));
  }
}

function _populateCollectionFilter() {
  const btn  = document.getElementById('collectionFilterBtn');
  const menu = document.getElementById('collectionFilterMenu');
  if (!btn || !menu) return;

  menu.replaceChildren();

  const allLink = h('a', { cls: 'dropdown-item small' + (App.activeCollection ? '' : ' active'), href: '#', text: 'All collections' });
  allLink.addEventListener('click', e => {
    e.preventDefault();
    onCollectionFilterChange('');
    btn.textContent = 'All collections';
    menu.classList.remove('show');
  });
  menu.appendChild(h('li', null, allLink));

  (App.collections || []).forEach(c => {
    const link = h('a', { cls: 'dropdown-item small py-1' + (App.activeCollection === c.id ? ' active' : ''), href: '#', style: 'line-height:1.3' });
    link.appendChild(document.createTextNode(c.name));
    if (c.name_ru) link.appendChild(h('span', { cls: 'text-muted d-block', style: 'font-size:11px', text: c.name_ru }));
    link.addEventListener('click', e => {
      e.preventDefault();
      onCollectionFilterChange(c.id);
      btn.textContent = c.name;
      menu.classList.remove('show');
    });
    menu.appendChild(h('li', null, link));
  });

  // Update button label to reflect current active collection
  const active = (App.collections || []).find(c => c.id === App.activeCollection);
  btn.textContent = active ? active.name : 'All collections';
}

function onCollectionFilterChange(val) {
  App.activeCollection = val || null;
  loadSeries(true);
  _pushState();
}

function _buildCollectionItem(c) {
  const countParts = [];
  if (c.series_total > 0) {
    const byStatus = c.series_by_status || {};
    const statusParts = Object.entries(byStatus)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([s, n]) => n + ' ' + s);
    countParts.push(c.series_total + ' series' + (statusParts.length ? ': ' + statusParts.join(' · ') : ''));
  } else {
    countParts.push('0 series');
  }

  const nameEl = h('span', { cls: 'fw-medium', text: c.name });
  const nameRuEl = c.name_ru ? h('span', { cls: 'text-muted small ms-1', text: '/ ' + c.name_ru }) : null;
  const countEl = h('span', { cls: 'text-muted small ms-2', text: countParts[0] });

  const filterBtn = h('button', { cls: 'btn btn-xs btn-outline-primary', title: 'Filter series by this collection', 'aria-label': 'Filter series by this collection' });
  filterBtn.appendChild(icon('bi bi-funnel'));
  filterBtn.addEventListener('click', () => {
    onCollectionFilterChange(c.id);
    const wrap = document.getElementById('collectionFilterWrap');
    _populateCollectionFilter();
  });

  const editBtn = h('button', { cls: 'btn btn-xs btn-outline-secondary' });
  editBtn.appendChild(icon('bi bi-pencil'));
  editBtn.addEventListener('click', () => {
    const nameInput = h('input', { type: 'text', cls: 'form-control form-control-sm', placeholder: 'Name (EN)', style: 'width:160px' });
    nameInput.value = c.name;
    const nameRuInput = h('input', { type: 'text', cls: 'form-control form-control-sm', placeholder: 'Name (RU)', style: 'width:160px' });
    nameRuInput.value = c.name_ru || '';
    const saveBtn = h('button', { cls: 'btn btn-xs btn-primary ms-1', text: 'Save' });
    saveBtn.addEventListener('click', async () => {
      try {
        await apiFetch('PATCH', '/api/collections/' + c.id, {
          name: nameInput.value.trim(),
          name_ru: nameRuInput.value.trim() || null,
        });
        showToast('Saved', 'success');
        await refreshCollections();
      } catch (e) { showToast(e.message, 'danger'); }
    });
    nameEl.replaceWith(h('span', { cls: 'd-flex gap-1 align-items-center' }, nameInput, nameRuInput, saveBtn));
  });

  const delBtn = h('button', { cls: 'btn btn-xs btn-outline-danger' });
  delBtn.appendChild(icon('bi bi-trash'));
  delBtn.addEventListener('click', () => showConfirm('Delete collection "' + c.name + '"? Series will be unassigned.', async () => {
    try {
      await apiFetch('DELETE', '/api/collections/' + c.id);
      showToast('Deleted', 'success');
      if (App.activeCollection === c.id) { App.activeCollection = null; loadSeries(true); }
      await refreshCollections();
    } catch (e) { showToast(e.message, 'danger'); }
  }));

  return h('div', { cls: 'card' },
    h('div', { cls: 'card-body py-2 px-3 d-flex align-items-center gap-2' },
      nameEl, nameRuEl, countEl,
      h('div', { cls: 'ms-auto d-flex gap-1' }, filterBtn, editBtn, delBtn)));
}

async function createCollection() {
  const input = document.getElementById('newCollectionName');
  const inputRu = document.getElementById('newCollectionNameRu');
  if (!input) return;
  const name = input.value.trim();
  if (!name) { showToast('Enter a collection name', 'danger'); return; }
  const name_ru = inputRu?.value.trim() || null;
  try {
    await apiFetch('POST', '/api/collections', { name, name_ru });
    input.value = '';
    if (inputRu) inputRu.value = '';
    showToast('Collection created', 'success');
    await refreshCollections();
  } catch (e) { showToast(e.message, 'danger'); }
}

// ── Trash ─────────────────────────────────────────────────────────────────────
function _disableWithSpinner(btn) {
  btn.disabled = true;
  btn.replaceChildren(h('span', { cls: 'spinner-border spinner-border-sm' }));
}

async function refreshTrash() {
  const content = document.getElementById('trashContent');
  const emptyBtn = document.getElementById('emptyTrashBtn');
  content.replaceChildren(h('div', { cls: 'text-muted text-center py-4', text: 'Loading…' }));
  try {
    const data = await apiFetch('GET', '/api/trash');
    const isEmpty = !data.series.length && !data.images.length;
    emptyBtn.classList.toggle('d-none', isEmpty);
    emptyBtn.onclick = () => showConfirm('Permanently delete everything in Trash?', async () => {
      const progressContainer = document.getElementById('trashProgressContainer');
      const progressBar = document.getElementById('trashProgressBar');
      const progressLabel = document.getElementById('trashProgressLabel');
      const progressCount = document.getElementById('trashProgressCount');
      const items = [
        ...data.series.map(s => ({ type: 'series', id: s.id, label: s.title || s.original_folder_name || s.id.slice(0, 8) })),
        ...data.images.map(i => ({ type: 'images', id: i.id, label: i.original_filename })),
      ];
      const total = items.length;
      _disableWithSpinner(emptyBtn);
      progressBar.style.width = '0%';
      progressContainer.classList.remove('d-none');
      let done = 0, failed = 0;
      for (const item of items) {
        progressLabel.textContent = item.label;
        progressCount.textContent = (done + 1) + ' / ' + total;
        try {
          await apiFetch('DELETE', '/api/trash/' + item.type + '/' + item.id);
        } catch (_) { failed++; }
        done++;
        const pct = Math.round(done / total * 100);
        progressBar.style.width = pct + '%';
        progressBar.setAttribute('aria-valuenow', pct);
      }
      progressContainer.classList.add('d-none');
      if (failed) showToast(failed + ' item(s) failed to delete', 'danger');
      else showToast('Trash emptied', 'success');
      refreshTrash();
    });
    if (isEmpty) {
      content.replaceChildren(h('p', { cls: 'text-muted text-center py-4', text: 'Trash is empty' }));
      return;
    }
    const nodes = [];
    if (data.series.length) {
      nodes.push(h('h6', { cls: 'text-muted small text-uppercase mb-2', text: 'Deleted Series' }));
      data.series.forEach(s => nodes.push(_buildTrashSeriesItem(s)));
    }
    if (data.images.length) {
      nodes.push(h('h6', { cls: 'text-muted small text-uppercase mb-2 mt-3', text: 'Deleted Images' }));
      data.images.forEach(i => nodes.push(_buildTrashImageItem(i)));
    }
    content.replaceChildren(...nodes);
  } catch (e) {
    content.replaceChildren(h('p', { cls: 'text-danger', text: e.message }));
  }
}

function _buildTrashSeriesItem(s) {
  const restoreBtn = h('button', { cls: 'btn btn-xs btn-outline-success me-1' });
  restoreBtn.appendChild(icon('bi bi-arrow-counterclockwise me-1'));
  restoreBtn.appendChild(document.createTextNode('Restore'));
  restoreBtn.addEventListener('click', async () => {
    _disableWithSpinner(restoreBtn);
    try {
      await apiFetch('POST', '/api/trash/series/' + s.id + '/restore');
      showToast('Series restored', 'success');
      loadSeries(true);
    } catch (e) { showToast(e.message, 'danger'); }
    refreshTrash();
  });
  const delBtn = h('button', { cls: 'btn btn-xs btn-outline-danger' });
  delBtn.appendChild(icon('bi bi-trash me-1'));
  delBtn.appendChild(document.createTextNode('Delete'));
  delBtn.addEventListener('click', () => showConfirm(
    'Permanently delete this series and all its images?',
    async () => {
      _disableWithSpinner(delBtn);
      try {
        await apiFetch('DELETE', '/api/trash/series/' + s.id);
        showToast('Permanently deleted', 'success');
      } catch (e) { showToast(e.message, 'danger'); }
      refreshTrash();
    }
  ));
  const title = s.title || s.original_folder_name || s.id.slice(0, 8);
  const thumb = s.cover_url
    ? Object.assign(document.createElement('img'), {
        src: s.cover_url, className: 'rounded flex-shrink-0',
        width: 48, height: 42,
        style: 'width:48px;height:42px;object-fit:cover',
      })
    : h('div', { cls: 'bg-secondary rounded flex-shrink-0', style: 'width:48px;height:42px' });
  return h('div', { cls: 'card mb-2' },
    h('div', { cls: 'card-body py-2 px-3 d-flex align-items-center gap-3' },
      thumb,
      h('div', { cls: 'flex-grow-1 overflow-hidden' },
        h('div', { cls: 'fw-medium text-truncate', text: title }),
        h('div', { cls: 'text-muted small', text: s.image_count + ' images · deleted ' + _timeAgo(s.deleted_at) })),
      h('div', { cls: 'd-flex gap-1 flex-shrink-0' }, restoreBtn, delBtn)));
}

function _buildTrashImageItem(i) {
  const restoreBtn = h('button', { cls: 'btn btn-xs btn-outline-success me-1' });
  restoreBtn.appendChild(icon('bi bi-arrow-counterclockwise me-1'));
  restoreBtn.appendChild(document.createTextNode('Restore'));
  restoreBtn.addEventListener('click', async () => {
    _disableWithSpinner(restoreBtn);
    try {
      await apiFetch('POST', '/api/trash/images/' + i.id + '/restore');
      showToast('Image restored', 'success');
      if (App.currentSeriesId === i.series_id) loadSeriesDetail(i.series_id);
    } catch (e) { showToast(e.message, 'danger'); }
    refreshTrash();
  });
  const delBtn = h('button', { cls: 'btn btn-xs btn-outline-danger' });
  delBtn.appendChild(icon('bi bi-trash me-1'));
  delBtn.appendChild(document.createTextNode('Delete'));
  delBtn.addEventListener('click', () => showConfirm('Permanently delete this image?', async () => {
    _disableWithSpinner(delBtn);
    try {
      await apiFetch('DELETE', '/api/trash/images/' + i.id);
      showToast('Permanently deleted', 'success');
    } catch (e) { showToast(e.message, 'danger'); }
    refreshTrash();
  }));
  const thumb = Object.assign(document.createElement('img'), {
    src: i.public_url, className: 'rounded flex-shrink-0',
    width: 48, height: 42,
    style: 'width:48px;height:42px;object-fit:cover',
  });
  return h('div', { cls: 'card mb-2' },
    h('div', { cls: 'card-body py-2 px-3 d-flex align-items-center gap-3' },
      thumb,
      h('div', { cls: 'flex-grow-1 overflow-hidden' },
        h('div', { cls: 'fw-medium text-truncate small', text: i.original_filename }),
        h('div', { cls: 'text-muted small', text: 'from "' + i.series_title + '" · deleted ' + _timeAgo(i.deleted_at) })),
      h('div', { cls: 'd-flex gap-1 flex-shrink-0' }, restoreBtn, delBtn)));
}

function _timeAgo(iso) {
  const secs = Math.floor((Date.now() - new Date(iso + 'Z')) / 1000);
  if (secs < 60) return 'just now';
  if (secs < 3600) return Math.floor(secs / 60) + 'm ago';
  if (secs < 86400) return Math.floor(secs / 3600) + 'h ago';
  return Math.floor(secs / 86400) + 'd ago';
}

// ── Draft helpers ─────────────────────────────────────────────────────────────
function getDraftEdits() {
  return {
    title:   document.getElementById('editorTitle')?.value,
    desc_en: document.getElementById('f_desc_en')?.value,
    desc_ru: document.getElementById('f_desc_ru')?.value,
    tags_ig: document.getElementById('f_tags_ig')?.value,
    tags_tg: document.getElementById('f_tags_tg')?.value,
  };
}

// ── URL state ─────────────────────────────────────────────────────────────────
const _DEFAULT_STATUSES = 'approved,draft,new';

function _seriesUrlLabel() {
  const s = App.currentSeries;
  return (s && (s.name || s.title)) || null;
}

function _pushState() {
  const statusStr = [...App.activeStatuses].sort().join(',');
  const label = _seriesUrlLabel();
  const p = new URLSearchParams();
  if (App.currentView && App.currentView !== 'editor') p.set('view', App.currentView);
  if (App.currentSeriesId) p.set('series', label || App.currentSeriesId);
  if (statusStr !== _DEFAULT_STATUSES) p.set('status', statusStr);
  if (App.search) p.set('q', App.search);
  if (App.activeCollection) p.set('collection', App.activeCollection);
  if (App.limit !== 15) p.set('limit', String(App.limit));
  const url = p.toString() ? '?' + p.toString() : location.pathname;
  history.pushState({
    view: App.currentView, series: App.currentSeriesId,
    status: statusStr, q: App.search,
    collection: App.activeCollection, limit: App.limit,
  }, '', url);
}

async function _resolveSeriesParam(param) {
  if (!param) return null;
  if (/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(param)) return param;
  const norm = param.toLowerCase();
  const inPage = App.series.find(s => (s.name || s.title || '').toLowerCase() === norm);
  if (inPage) return inPage.id;
  try {
    const data = await apiFetch('GET', '/api/series?search=' + encodeURIComponent(param) + '&limit=5&status=new,draft,approved,posted,skip');
    const match = (data.items || []).find(s => (s.name || s.title || '').toLowerCase() === norm);
    return match?.id || null;
  } catch { return null; }
}

function _syncFiltersFromState(status, q, collection, limit) {
  if (status) App.activeStatuses = new Set(status.split(','));
  App.search = q || '';
  App.activeCollection = collection || null;
  App.limit = limit || 15;
  document.querySelectorAll('#statusFilterMenu input').forEach(cb => {
    cb.checked = App.activeStatuses.has(cb.value);
  });
  document.getElementById('limitSel').value = String(App.limit);
  const searchEl = document.getElementById('seriesSearch');
  if (searchEl) searchEl.value = App.search;
  if (App.collections.length) _populateCollectionFilter();
}

async function _restoreFromUrl() {
  const p = new URLSearchParams(location.search);
  const view = p.get('view') || 'editor';
  const seriesParam = p.get('series') || null;
  _syncFiltersFromState(p.get('status'), p.get('q'), p.get('collection'), parseInt(p.get('limit')) || null);

  showView(view, { push: false });
  await loadSeries(true);
  if (seriesParam) {
    const seriesId = await _resolveSeriesParam(seriesParam);
    if (seriesId) await selectSeries(seriesId, { push: false });
  }

  _pushState();
}

// ── Init ──────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
  apiFetch('GET', '/api/settings/providers').then(d => { PROVIDER_MODELS = d; }).catch(() => {});
  apiFetch('GET', '/api/collections').then(data => { App.collections = data; _populateCollectionFilter(); }).catch(() => {});
  initLightbox();
  const filterBtn  = document.getElementById('filterBtn');
  const filterMenu = document.getElementById('statusFilterMenu');
  filterBtn.addEventListener('click', e => {
    e.stopPropagation();
    const open = filterMenu.classList.contains('show');
    if (!open) {
      const r = filterBtn.getBoundingClientRect();
      filterMenu.style.position = 'fixed';
      filterMenu.style.top      = r.bottom + 'px';
      filterMenu.style.left     = 'auto';
      filterMenu.style.right    = (window.innerWidth - r.right) + 'px';
    }
    filterMenu.classList.toggle('show');
    filterBtn.setAttribute('aria-expanded', String(!open));
  });
  document.addEventListener('click', () => {
    filterMenu.classList.remove('show');
    filterBtn.setAttribute('aria-expanded', 'false');
  });

  const collFilterBtn  = document.getElementById('collectionFilterBtn');
  const collFilterMenu = document.getElementById('collectionFilterMenu');
  collFilterBtn.addEventListener('click', e => {
    e.stopPropagation();
    const open = collFilterMenu.classList.contains('show');
    if (!open) {
      const r = collFilterBtn.getBoundingClientRect();
      collFilterMenu.style.position = 'fixed';
      collFilterMenu.style.top  = r.bottom + 'px';
      collFilterMenu.style.left = r.left + 'px';
      collFilterMenu.style.right = 'auto';
    }
    collFilterMenu.classList.toggle('show');
  });
  document.addEventListener('click', () => collFilterMenu.classList.remove('show'));

  document.getElementById('limitSel').addEventListener('change', function () {
    App.limit = +this.value;
    loadSeries(true);
    _pushState();
  });

  window.addEventListener('popstate', async (e) => {
    const s = e.state;
    if (!s) return;
    _syncFiltersFromState(s.status, s.q, s.collection, s.limit);
    showView(s.view || 'editor', { push: false });
    await loadSeries(true);
    if (s.series) await selectSeries(s.series, { push: false });
  });

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

  await _restoreFromUrl();
});
