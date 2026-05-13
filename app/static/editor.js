// ── Selection state ───────────────────────────────────────────────────────────
let _selectedImages = new Set();

function _debounce(fn, ms) { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; }

// ── Editor entry point ────────────────────────────────────────────────────────
function renderEditor(series) {
  _selectedImages = new Set(series.images.filter(i => i.status === 'queued').map(i => i.id));

  const titleInput = h('input', {
    type: 'text', cls: 'form-control form-control-sm fw-semibold',
    id: 'editorTitle', placeholder: 'Series title...',
  });
  titleInput.value = series.title || '';
  titleInput.addEventListener('blur', () => saveTitle(series.id));

  const titleRow = h('div', { cls: 'd-flex align-items-center gap-2 mb-3' }, titleInput);
  if (series.original_folder_name) {
    const note = h('span', { cls: 'text-muted small text-truncate flex-shrink-1', style: 'max-width:180px', text: series.original_folder_name });
    note.title = series.original_folder_name;
    titleRow.appendChild(note);
  }

  document.getElementById('editorPanel').replaceChildren(
    titleRow,
    buildImagesCard(series),
    buildDescriptionsCard(series),
    buildGenerateCard(series.id),
    buildActionsCard(series),
  );

  initImageSortable(series.id);
  restoreDraft(series.id);
}

async function saveTitle(seriesId) {
  const val = document.getElementById('editorTitle')?.value?.trim() ?? '';
  if (val === (App.currentSeries?.title ?? '')) return;
  try {
    const updated = await apiFetch('PUT', '/api/series/' + seriesId, { title: val });
    App.currentSeries = updated;
    updateSeriesItem(updated);
  } catch (e) { showToast(e.message, 'danger'); }
}

// ── Images card ───────────────────────────────────────────────────────────────
function buildImagesCard(series) {
  const addBtn = h('button', { cls: 'btn btn-xs btn-outline-secondary' });
  addBtn.appendChild(icon('bi bi-plus'));
  addBtn.appendChild(document.createTextNode(' Add'));
  addBtn.addEventListener('click', () => addImages(series.id));

  const headerLabel = h('span', { cls: 'small fw-medium', id: 'imagesCardLabel' });
  headerLabel.appendChild(icon('bi bi-images me-1'));
  headerLabel.appendChild(document.createTextNode(_imagesCountLabel(series.images.length)));

  const strip = h('div', { id: 'imageStrip', cls: 'd-flex gap-2', style: 'min-height:160px;overflow-x:auto;flex-wrap:nowrap;padding-bottom:4px' });
  if (!series.images.length) {
    strip.appendChild(h('span', { cls: 'text-muted small align-self-center p-2', text: 'No images yet' }));
  } else {
    const _group = s => _selectedImages.has(s.id) ? 0 : s.status === 'posted' ? 2 : s.status === 'skip' ? 3 : 1;
    [...series.images].sort((a, b) => _group(a) - _group(b))
      .forEach(img => strip.appendChild(buildThumb(img, series.id)));
  }

  return h('div', { cls: 'card mb-3' },
    h('div', { cls: 'card-header d-flex justify-content-between align-items-center py-2' }, headerLabel, addBtn),
    h('div', { cls: 'card-body p-2' }, strip, buildActionBar(series.id)));
}

function _imagesCountLabel(total) {
  const sel = _selectedImages.size;
  return sel > 0
    ? 'Images (' + sel + ' selected / ' + total + ')'
    : 'Images (' + total + ')';
}

function _refreshImagesHeader(total) {
  const el = document.getElementById('imagesCardLabel');
  if (!el) return;
  el.replaceChildren(icon('bi bi-images me-1'), document.createTextNode(_imagesCountLabel(total)));
}

function buildThumb(img, seriesId) {
  const imgEl = document.createElement('img');
  imgEl.setAttribute('src', img.public_url);
  imgEl.className = 'rounded';
  imgEl.style.cssText = 'width:160px;height:140px;object-fit:cover';
  imgEl.loading = 'lazy';
  imgEl.setAttribute('draggable', 'false');
  imgEl.style.cursor = 'zoom-in';
  imgEl.addEventListener('click', e => {
    e.stopPropagation();
    const strip = document.getElementById('imageStrip');
    const thumbs = [...strip.querySelectorAll('[data-image-id]')];
    const images = thumbs.map(el => ({
      id: el.dataset.imageId,
      public_url: el.querySelector('img').getAttribute('src'),
      status: el.dataset.imageStatus || 'pending',
    }));
    const idx = thumbs.findIndex(el => el.dataset.imageId === img.id);
    openLightbox(images, idx >= 0 ? idx : 0);
  });

  const menuBtn = h('button', { cls: 'btn btn-xs btn-dark opacity-75', text: '⋯' });
  menuBtn.setAttribute('data-bs-toggle', 'dropdown');
  menuBtn.addEventListener('click', e => e.stopPropagation());

  const dropItems = document.createElement('ul');
  dropItems.className = 'dropdown-menu dropdown-menu-end';

  // "Move to" header + items
  const hdr = document.createElement('li');
  hdr.appendChild(h('h6', { cls: 'dropdown-header', text: 'Move to' }));
  dropItems.appendChild(hdr);
  buildMoveToItems(img.id, seriesId, false).forEach(li => dropItems.appendChild(li));
  const divLi = document.createElement('li');
  divLi.appendChild(h('hr', { cls: 'dropdown-divider' }));
  dropItems.appendChild(divLi);

  const delLi = document.createElement('li');
  const delA = h('a', { cls: 'dropdown-item small text-danger', href: '#' });
  delA.appendChild(icon('bi bi-trash me-1'));
  delA.appendChild(document.createTextNode('Delete'));
  delA.addEventListener('click', e => { e.preventDefault(); deleteImage(img.id); });
  delLi.appendChild(delA);
  dropItems.appendChild(delLi);

  const gripEl = h('div', { cls: 'thumb-grip position-absolute' });
  gripEl.appendChild(icon('bi bi-grip-vertical'));

  const statusBtn = h('button', {
    cls: 'btn btn-xs position-absolute top-0 start-0 m-1 p-1 border-0 bg-transparent',
    style: 'line-height:1',
    'data-select-btn': img.id,
  });
  statusBtn.appendChild(icon(_selectIcon(img.id, img.status)));
  statusBtn.addEventListener('click', e => {
    e.stopPropagation();
    _toggleSelection(img.id, img.status, seriesId);
  });

  const isSelected = _selectedImages.has(img.id);
  const outerCls = 'position-relative flex-shrink-0' +
    (img.status === 'posted' ? ' thumb-posted' : '') +
    (img.status === 'skip' ? ' thumb-skip' : '') +
    (isSelected ? ' thumb-selected' : '');
  return h('div', { cls: outerCls, 'data-image-id': img.id, 'data-image-status': img.status },
    imgEl,
    statusBtn,
    gripEl,
    h('div', { cls: 'position-absolute top-0 end-0 m-1' },
      h('div', { cls: 'dropdown' }, menuBtn, dropItems)));
}

function _selectIcon(imgId, status) {
  if (_selectedImages.has(imgId)) return 'bi bi-check-circle-fill text-primary fs-5';
  if (status === 'posted') return 'bi bi-check-circle-fill text-success fs-5';
  return 'bi bi-circle text-white fs-5';
}

function _toggleSelection(imgId, imgStatus, seriesId) {
  if (imgStatus === 'posted') return;
  const isNowSelected = !_selectedImages.has(imgId);
  if (isNowSelected) _selectedImages.add(imgId); else _selectedImages.delete(imgId);
  const btn = document.querySelector('[data-select-btn="' + imgId + '"]');
  if (btn) { btn.replaceChildren(icon(_selectIcon(imgId, imgStatus))); }
  const thumb = document.querySelector('[data-image-id="' + imgId + '"]');
  if (thumb) thumb.classList.toggle('thumb-selected', isNowSelected);
  _resortStrip();
  const total = App.currentSeries?.images?.length ?? 0;
  _refreshImagesHeader(total);
  _refreshActionBar(seriesId);
  _lightboxSyncSelectBtn(imgId);
}

function _resortStrip() {
  const strip = document.getElementById('imageStrip');
  if (!strip) return;
  const thumbs = [...strip.querySelectorAll('[data-image-id]')];
  if (!thumbs.length) return;
  const _g = el => {
    if (_selectedImages.has(el.dataset.imageId)) return 0;
    const s = el.dataset.imageStatus || 'pending';
    return s === 'posted' ? 2 : s === 'skip' ? 3 : 1;
  };
  thumbs
    .map((el, i) => ({ el, g: _g(el), i }))
    .sort((a, b) => a.g - b.g || a.i - b.i)
    .forEach(({ el }) => strip.appendChild(el));
}

// ── Move to picker ────────────────────────────────────────────────────────────
// Returns <li> elements for the "Move to" section.
// bulk=false → moves just imageId; bulk=true → moves all _selectedImages
function buildMoveToItems(imageId, seriesId, bulk, afterMove = null) {
  const items = [];

  const mkItem = (label, iconCls, onClick) => {
    const li = document.createElement('li');
    const a = h('a', { cls: 'dropdown-item small', href: '#' });
    if (iconCls) a.appendChild(icon(iconCls + ' me-1'));
    a.appendChild(document.createTextNode(label));
    a.addEventListener('click', e => { e.preventDefault(); onClick(); });
    li.appendChild(a);
    return li;
  };

  // Unsorted — always pinned first
  items.push(mkItem('Unsorted', 'bi bi-folder', async () => {
    try {
      const s = await _getOrCacheUnsorted();
      const ids = bulk ? [..._selectedImages] : [imageId];
      if (await moveImages(ids, s.id, seriesId)) {
        if (afterMove) afterMove();
      }
    } catch (e) { showToast(e.message, 'danger'); }
  }));

  const activeStatuses = ['new', 'draft', 'approved', 'scheduled', 'partial_posted'];
  const _isUnsorted = s => s.title === 'Unsorted' || (App.unsortedSeriesId && s.id === App.unsortedSeriesId);
  const active = App.series.filter(s => s.id !== seriesId && !_isUnsorted(s) && activeStatuses.includes(s.status));

  // Always show search/create input; ≤10 series → filter client-side, >10 → fetch API
  const li = document.createElement('li');
  li.className = 'px-2 py-1';
  const input = h('input', { type: 'text', cls: 'form-control form-control-sm', placeholder: 'Search or create series…' });
  input.setAttribute('autocomplete', 'off');
  const results = h('ul', { cls: 'list-unstyled mb-0 mt-1', style: 'max-height:160px;overflow-y:auto' });

  const renderRow = (s) => {
    const name = s.title || s.original_folder_name || s.id.slice(0, 8);
    const row = h('li', null, h('a', { cls: 'dropdown-item small', href: '#', text: name }));
    row.firstChild.addEventListener('click', async e => {
      e.preventDefault();
      const ids = bulk ? [..._selectedImages] : [imageId];
      if (await moveImages(ids, s.id, seriesId)) {
        if (afterMove) afterMove();
      }
    });
    return row;
  };

  const appendCreate = (query) => {
    const createRow = h('li', null, h('a', { cls: 'dropdown-item small text-primary', href: '#' }));
    createRow.firstChild.appendChild(icon('bi bi-plus me-1'));
    createRow.firstChild.appendChild(document.createTextNode('Create "' + query + '"'));
    createRow.firstChild.addEventListener('click', async e => {
      e.preventDefault();
      // Capture selection immediately — before any async call that might change state
      const ids = bulk ? [..._selectedImages] : [imageId];
      try {
        const newSeries = await apiFetch('POST', '/api/series', { title: query });
        App.series.push(newSeries);
        await Promise.all(ids.map(id => apiFetch('PUT', '/api/images/' + id + '/move', { target_series_id: newSeries.id })));
        _selectedImages.clear();
        // Update source series in sidebar, then open the new series
        const sourceUpdated = await apiFetch('GET', '/api/series/' + seriesId);
        updateSeriesItem(sourceUpdated);
        document.getElementById('seriesItems')?.prepend(buildSeriesItem(newSeries));
        await selectSeries(newSeries.id);
        updateSeriesItem(App.currentSeries);
        showToast(ids.length > 1 ? ids.length + ' images moved' : 'Image moved', 'success');
        if (afterMove) afterMove();
      } catch (err) { showToast(err.message, 'danger'); }
    });
    results.appendChild(createRow);
  };

  const renderResults = async (query) => {
    results.replaceChildren();
    if (App.total <= 10) {
      // client-side filter
      const filtered = query
        ? active.filter(s => (s.title || s.original_folder_name || '').toLowerCase().includes(query.toLowerCase()))
        : active;
      filtered.forEach(s => results.appendChild(renderRow(s)));
      if (query) {
        const exactMatch = active.some(s => (s.title || '').toLowerCase() === query.toLowerCase());
        if (!exactMatch) appendCreate(query);
      }
    } else {
      if (!query) return;
      try {
        const statusParam = activeStatuses.join(',');
        const data = await apiFetch('GET', '/api/series?search=' + encodeURIComponent(query) + '&status=' + statusParam + '&limit=10');
        const filtered = data.items.filter(s => s.id !== seriesId && !_isUnsorted(s));
        filtered.forEach(s => results.appendChild(renderRow(s)));
        const exactMatch = filtered.some(s => (s.title || '').toLowerCase() === query.toLowerCase());
        if (!exactMatch) appendCreate(query);
      } catch (e) { showToast(e.message, 'danger'); }
    }
  };

  // show all active series immediately (≤10 mode only)
  if (App.total <= 10) renderResults('');

  const debouncedSearch = _debounce(renderResults, 280);
  input.addEventListener('input', e => debouncedSearch(e.target.value.trim()));
  input.addEventListener('click', e => e.stopPropagation());
  li.appendChild(input);
  li.appendChild(results);
  items.push(li);

  return items;
}

async function _getOrCacheUnsorted() {
  if (!App.unsortedSeriesId) {
    const s = await apiFetch('GET', '/api/series/unsorted');
    App.unsortedSeriesId = s.id;
    return s;
  }
  return { id: App.unsortedSeriesId };
}

// ── Action bar ────────────────────────────────────────────────────────────────
function buildActionBar(seriesId) {
  const bar = h('div', { id: 'imageActionBar', cls: 'd-flex align-items-center gap-2 flex-wrap mt-2 pt-2 border-top' });
  if (_selectedImages.size === 0) { bar.classList.add('d-none'); return bar; }

  bar.appendChild(h('span', { cls: 'small text-muted', text: _selectedImages.size + ' selected' }));

  // Move to dropdown
  const moveBtn = h('button', { cls: 'btn btn-xs btn-outline-secondary' });
  moveBtn.appendChild(icon('bi bi-box-arrow-right me-1'));
  moveBtn.appendChild(document.createTextNode('Move to…'));
  moveBtn.setAttribute('data-bs-toggle', 'dropdown');

  const moveDropItems = document.createElement('ul');
  moveDropItems.className = 'dropdown-menu';
  buildMoveToItems(null, seriesId, true).forEach(li => moveDropItems.appendChild(li));

  bar.appendChild(h('div', { cls: 'dropdown' }, moveBtn, moveDropItems));

  // Skip / Unskip — shown based on what's selected
  const statusMap = new Map((App.currentSeries?.images ?? []).map(i => [i.id, i.status]));
  const toSkip   = [..._selectedImages].filter(id => { const s = statusMap.get(id); return s && s !== 'skip' && s !== 'posted'; });
  const toUnskip = [..._selectedImages].filter(id => statusMap.get(id) === 'skip');

  const _mkStatusAction = (label, iconCls, ids, newStatus) => {
    const btn = h('button', { cls: 'btn btn-xs btn-outline-secondary' });
    btn.appendChild(icon(iconCls + ' me-1'));
    btn.appendChild(document.createTextNode(label));
    btn.addEventListener('click', async () => {
      try {
        await Promise.all(ids.map(id => apiFetch('PATCH', '/api/images/' + id + '/status', { status: newStatus })));
        const updated = await apiFetch('GET', '/api/series/' + seriesId);
        App.currentSeries = updated;
        renderEditor(updated);
      } catch (e) { showToast(e.message, 'danger'); }
    });
    return btn;
  };

  if (toSkip.length > 0)   bar.appendChild(_mkStatusAction('Skip',   'bi bi-eye-slash', toSkip,   'skip'));
  if (toUnskip.length > 0) bar.appendChild(_mkStatusAction('Unskip', 'bi bi-eye',       toUnskip, 'pending'));

  // Delete selected
  const delBtn = h('button', { cls: 'btn btn-xs btn-outline-danger' });
  delBtn.appendChild(icon('bi bi-trash me-1'));
  delBtn.appendChild(document.createTextNode('Delete'));
  delBtn.addEventListener('click', () => {
    showConfirm('Delete ' + _selectedImages.size + ' image(s)?', async () => {
      try {
        const toDelete = [..._selectedImages];
        await Promise.all(toDelete.map(id => apiFetch('DELETE', '/api/images/' + id)));
        const updated = await apiFetch('GET', '/api/series/' + seriesId);
        App.currentSeries = updated;
        renderEditor(updated);
        showToast('Moved to Trash', 'success');
      } catch (e) { showToast(e.message, 'danger'); }
    });
  });
  bar.appendChild(delBtn);

  // Save (persist selection as queued)
  const saveBtn = h('button', { cls: 'btn btn-xs btn-outline-primary' });
  saveBtn.appendChild(icon('bi bi-floppy me-1'));
  saveBtn.appendChild(document.createTextNode('Save'));
  saveBtn.addEventListener('click', async () => {
    try {
      const updated = await apiFetch('PUT', '/api/series/' + seriesId + '/queue', { image_ids: [..._selectedImages] });
      App.currentSeries = updated;
      updateSeriesItem(updated);
      showToast('Queue saved', 'success');
    } catch (e) { showToast(e.message, 'danger'); }
  });
  bar.appendChild(saveBtn);

  return bar;
}

function _refreshActionBar(seriesId) {
  const old = document.getElementById('imageActionBar');
  if (old) old.replaceWith(buildActionBar(seriesId));
}

let _sortable = null;
let _lightboxImages = [];
let _lightboxIdx    = 0;
let _lightboxOpen   = false;

function initImageSortable(seriesId) {
  const strip = document.getElementById('imageStrip');
  if (!strip) return;
  if (_sortable) { _sortable.destroy(); _sortable = null; }
  const touch = window.matchMedia('(pointer: coarse)').matches;
  _sortable = Sortable.create(strip, {
    animation: 150,
    ghostClass: 'sortable-ghost',
    ...(touch
      ? { delay: 300, forceFallback: true, touchStartThreshold: 8 }
      : { handle: '.thumb-grip', touchStartThreshold: 4 }),
    onEnd: async () => {
      const ids = [...strip.querySelectorAll('[data-image-id]')].map(el => el.dataset.imageId);
      try {
        await apiFetch('PUT', '/api/series/' + seriesId + '/images/reorder', { image_ids: ids });
      } catch (e) { showToast('Reorder failed: ' + e.message, 'danger'); }
    },
  });
  if (touch) strip.addEventListener('contextmenu', e => e.preventDefault());
}

function initLightbox() {
  document.addEventListener('keydown', e => {
    if (!_lightboxOpen) return;
    if (e.key === 'ArrowLeft')  lightboxNav(-1);
    if (e.key === 'ArrowRight') lightboxNav(+1);
  });
  document.getElementById('lightboxModal')
    .addEventListener('hidden.bs.modal', () => { _lightboxOpen = false; });
  document.getElementById('lightboxPrev').addEventListener('click', () => lightboxNav(-1));
  document.getElementById('lightboxNext').addEventListener('click', () => lightboxNav(+1));

  let _touchStartX = 0;
  const modal = document.getElementById('lightboxModal');
  modal.addEventListener('touchstart', e => { _touchStartX = e.changedTouches[0].clientX; }, { passive: true });
  modal.addEventListener('touchend', e => {
    if (!_lightboxOpen) return;
    const dx = e.changedTouches[0].clientX - _touchStartX;
    if (Math.abs(dx) > 50) lightboxNav(dx < 0 ? +1 : -1);
  }, { passive: true });

  async function _lightboxPatch(newStatus) {
    const img = _lightboxImages[_lightboxIdx];
    try {
      const updated = await apiFetch('PATCH', '/api/images/' + img.id + '/status', { status: newStatus });
      _lightboxImages[_lightboxIdx] = { ...img, status: newStatus };
      // preserve frontend selection across re-render; remove patched image if it became skip/posted
      const savedSelection = new Set(_selectedImages);
      if (newStatus === 'skip' || newStatus === 'posted') savedSelection.delete(img.id);
      App.currentSeries = updated;
      renderEditor(updated);
      // restore selection (renderEditor re-inits from DB queued; we override with saved)
      _selectedImages = savedSelection;
      _lightboxRender();
    } catch (err) { showToast(err.message, 'danger'); }
  }

  document.getElementById('lightboxQueueBtn').addEventListener('click', () => {
    const img = _lightboxImages[_lightboxIdx];
    if (img.status === 'posted') return;
    const seriesId = App.currentSeriesId;
    _toggleSelection(img.id, img.status, seriesId);
    _lightboxRender();
  });
  document.getElementById('lightboxSkipBtn').addEventListener('click', () => {
    const img = _lightboxImages[_lightboxIdx];
    _lightboxPatch(img.status === 'skip' ? 'pending' : 'skip');
  });
  document.getElementById('lightboxDeleteBtn').addEventListener('click', async () => {
    const img = _lightboxImages[_lightboxIdx];
    try {
      const updated = await apiFetch('DELETE', '/api/images/' + img.id);
      _lightboxImages.splice(_lightboxIdx, 1);
      if (!_lightboxImages.length) {
        bootstrap.Modal.getOrCreateInstance(document.getElementById('lightboxModal')).hide();
      } else {
        _lightboxIdx = Math.min(_lightboxIdx, _lightboxImages.length - 1);
        _lightboxRender();
      }
      App.currentSeries = updated;
      renderEditor(updated);
      showToast('Moved to Trash', 'success');
    } catch (err) { showToast(err.message, 'danger'); }
  });
}

function openLightbox(images, startIdx) {
  _lightboxImages = images;
  _lightboxIdx    = startIdx;
  _lightboxOpen   = true;
  _lightboxRender();
  bootstrap.Modal.getOrCreateInstance(document.getElementById('lightboxModal')).show();
}

function _lightboxRender() {
  const img = _lightboxImages[_lightboxIdx];
  document.getElementById('lightboxImg').setAttribute('src', img.public_url);
  document.getElementById('lightboxImg').setAttribute('alt', 'Image ' + (_lightboxIdx + 1));
  document.getElementById('lightboxCounter').textContent =
    (_lightboxIdx + 1) + ' / ' + _lightboxImages.length;
  const single = _lightboxImages.length <= 1;
  document.getElementById('lightboxPrev').classList.toggle('invisible', single);
  document.getElementById('lightboxNext').classList.toggle('invisible', single);

  const qBtn = document.getElementById('lightboxQueueBtn');
  const isSelected = _selectedImages.has(img.id);
  qBtn.replaceChildren(icon(isSelected ? 'bi bi-check-circle-fill me-1' : 'bi bi-circle me-1'),
    document.createTextNode(isSelected ? 'Deselect' : 'Select'));
  qBtn.disabled = img.status === 'posted';

  const sBtn = document.getElementById('lightboxSkipBtn');
  const isSkip = img.status === 'skip';
  sBtn.replaceChildren(icon(isSkip ? 'bi bi-eye me-1' : 'bi bi-eye-slash me-1'),
    document.createTextNode(isSkip ? 'Unskip' : 'Skip'));

  const moveMenu = document.getElementById('lightboxMoveMenu');
  if (moveMenu) {
    moveMenu.replaceChildren();
    buildMoveToItems(img.id, App.currentSeriesId, false, () => {
      _lightboxImages.splice(_lightboxIdx, 1);
      if (!_lightboxImages.length) {
        bootstrap.Modal.getOrCreateInstance(document.getElementById('lightboxModal')).hide();
      } else {
        _lightboxIdx = Math.min(_lightboxIdx, _lightboxImages.length - 1);
        _lightboxRender();
      }
    }).forEach(li => moveMenu.appendChild(li));
  }
}

function lightboxNav(delta) {
  _lightboxIdx = (_lightboxIdx + delta + _lightboxImages.length) % _lightboxImages.length;
  _lightboxRender();
}

function _lightboxSyncSelectBtn(imgId) {
  if (!_lightboxOpen) return;
  const current = _lightboxImages[_lightboxIdx];
  if (current && current.id === imgId) _lightboxRender();
}

async function addImages(seriesId) {
  const input = document.createElement('input');
  input.type = 'file'; input.multiple = true; input.accept = 'image/*';
  input.addEventListener('change', async () => {
    if (!input.files.length) return;
    const fd = new FormData();
    for (const f of input.files) fd.append('files', f);
    try {
      const resp = await fetch('/api/series/' + seriesId + '/images', { method: 'POST', body: fd });
      if (!resp.ok) { const e = await resp.json(); throw new Error(e.detail); }
      await loadSeriesDetail(seriesId);
      updateSeriesItem(App.currentSeries);
      showToast('Images uploaded', 'success');
    } catch (e) { showToast(e.message, 'danger'); }
  });
  input.click();
}

async function moveImages(imageIds, targetId, currentId) {
  try {
    await Promise.all(imageIds.map(id => apiFetch('PUT', '/api/images/' + id + '/move', { target_series_id: targetId })));
    _selectedImages.clear();
    await loadSeriesDetail(currentId);
    const t = await apiFetch('GET', '/api/series/' + targetId);
    updateSeriesItem(t);
    showToast(imageIds.length > 1 ? imageIds.length + ' images moved' : 'Image moved', 'success');
    return true;
  } catch (e) { showToast(e.message, 'danger'); }
}

async function deleteImage(imageId) {
  try {
    const updated = await apiFetch('DELETE', '/api/images/' + imageId);
    App.currentSeries = updated;
    renderEditor(updated);
    showToast('Moved to Trash', 'success');
  } catch (e) { showToast(e.message, 'danger'); }
}

async function deleteVariant(variantId) {
  try {
    const updated = await apiFetch('DELETE', '/api/ai_variants/' + variantId);
    App.currentSeries = updated;
    renderEditor(updated);
    showToast('Variant deleted', 'success');
  } catch (e) { showToast(e.message, 'danger'); }
}

// ── Descriptions card ─────────────────────────────────────────────────────────
function buildDescriptionsCard(series) {
  const variants = series.ai_variants || [];
  const variantBtns = h('div', { cls: 'd-flex gap-1 flex-wrap mb-2' });
  if (!variants.length) {
    variantBtns.appendChild(h('p', { cls: 'text-muted small mb-2', text: 'No AI variants yet.' }));
  } else {
    variants.forEach((v, i) => {
      const btn = h('button', {
        cls: 'btn btn-xs ' + (i === 0 ? 'btn-primary' : 'btn-outline-secondary'),
        'data-variant-idx': String(i),
        onclick: () => applyVariant(i),
      });
      btn.appendChild(document.createTextNode('V' + (variants.length - i) + ' '));
      btn.appendChild(h('span', { cls: 'opacity-75', style: 'font-size:10px', text: v.provider }));
      if (v.cost_usd > 0) btn.appendChild(h('span', { cls: 'opacity-50 ms-1', style: 'font-size:10px', text: '$' + v.cost_usd.toFixed(4) }));
      const delBtn = h('button', {
        cls: 'btn btn-xs btn-outline-danger px-1',
        title: 'Delete variant',
        onclick: (e) => { e.stopPropagation(); deleteVariant(v.id); },
      });
      delBtn.appendChild(document.createTextNode('×'));
      variantBtns.appendChild(h('span', { style: 'display:inline-flex;gap:2px;align-items:center' }, btn, delBtn));
    });
  }

  const descEn = h('textarea', { cls: 'form-control form-control-sm', id: 'f_desc_en', rows: '4' });
  descEn.value = series.description_en || '';
  const descRu = h('textarea', { cls: 'form-control form-control-sm', id: 'f_desc_ru', rows: '4' });
  descRu.value = series.description_ru || '';
  const tagsIg = h('textarea', { cls: 'form-control form-control-sm', id: 'f_tags_ig', rows: '2' });
  tagsIg.value = (series.tags_instagram || []).join(' ');
  const tagsTg = h('input', { type: 'text', cls: 'form-control form-control-sm', id: 'f_tags_tg' });
  tagsTg.value = (series.tags_telegram || []).join(' ');

  const saveBtn = h('button', { cls: 'btn btn-sm btn-primary' });
  saveBtn.appendChild(icon('bi bi-floppy me-1'));
  saveBtn.appendChild(document.createTextNode('Save'));
  saveBtn.addEventListener('click', () => saveDescription(series.id));

  const mkField = (lbl, ctrl) => h('div', { cls: 'col-12 col-lg-6' },
    h('label', { cls: 'form-label small mb-0', text: lbl }), ctrl);

  const form = h('div', { cls: 'row g-2' },
    mkField('Description EN (Instagram & FB Page)', descEn),
    mkField('Description RU (Telegram)', descRu),
    mkField('Instagram & FB Page tags', tagsIg),
    h('div', { cls: 'col-12 col-lg-6' }, h('label', { cls: 'form-label small mb-0', text: 'Telegram tags' }), tagsTg),
    h('div', { cls: 'col-12' }, saveBtn));

  const headerLabel = h('span', { cls: 'small fw-medium' });
  headerLabel.appendChild(icon('bi bi-card-text me-1'));
  headerLabel.appendChild(document.createTextNode('Descriptions'));

  return h('div', { cls: 'card mb-3' },
    h('div', { cls: 'card-header py-2' }, headerLabel),
    h('div', { cls: 'card-body p-2' }, variantBtns, form));
}

function applyVariant(idx) {
  const v = App.currentSeries?.ai_variants?.[idx];
  if (!v) return;
  const set = (id, val) => { const el = document.getElementById(id); if (el) el.value = val || ''; };
  set('f_desc_en', v.description_en);
  set('f_desc_ru', v.description_ru);
  set('f_tags_ig', (v.tags_instagram || []).join(' '));
  set('f_tags_tg', (v.tags_telegram  || []).join(' '));
  if (v.title) { const t = document.getElementById('editorTitle'); if (t) t.value = v.title; }
  const hintEl = document.getElementById('genHint'); if (hintEl) hintEl.value = v.hint || '';
  document.querySelectorAll('[data-variant-idx]').forEach((btn, i) => {
    btn.classList.toggle('btn-primary', i === idx);
    btn.classList.toggle('btn-outline-secondary', i !== idx);
  });
}

async function saveDescription(seriesId) {
  const tagsIg = (document.getElementById('f_tags_ig')?.value || '').split(/\s+/).filter(Boolean);
  const tagsTg = (document.getElementById('f_tags_tg')?.value || '').split(/\s+/).filter(Boolean);
  try {
    const updated = await apiFetch('PUT', '/api/series/' + seriesId, {
      title:          document.getElementById('editorTitle')?.value?.trim() || '',
      description_en: document.getElementById('f_desc_en')?.value || '',
      description_ru: document.getElementById('f_desc_ru')?.value || '',
      tags_instagram: tagsIg,
      tags_telegram:  tagsTg,
    });
    App.currentSeries = updated;
    updateSeriesItem(updated);
    const t = document.getElementById('editorTitle');
    if (t && updated.title) t.value = updated.title;
    localStorage.removeItem('draft_' + seriesId);
    showToast('Saved', 'success');
  } catch (e) { showToast(e.message, 'danger'); }
}

// ── Generate card ─────────────────────────────────────────────────────────────
function buildGenerateCard(seriesId) {
  const hintInput = h('input', { type: 'text', cls: 'form-control form-control-sm', id: 'genHint', placeholder: 'e.g. this is a fox spirit...' });
  const provSel = document.createElement('select');
  provSel.className = 'form-select form-select-sm'; provSel.id = 'genProvider'; provSel.style.width = '120px';
  [['', 'Default'], ['anthropic', 'Anthropic'], ['openai', 'OpenAI'], ['google', 'Google']].forEach(([val, lbl]) => {
    const o = document.createElement('option'); o.value = val; o.textContent = lbl; provSel.appendChild(o);
  });
  const modelSel = document.createElement('select');
  modelSel.className = 'form-select form-select-sm'; modelSel.id = 'genModel'; modelSel.style.width = '200px';
  buildProviderModelSelect(modelSel, '', { withDefault: true });
  provSel.addEventListener('change', () => buildProviderModelSelect(modelSel, provSel.value, { withDefault: true }));
  const genBtn = h('button', { cls: 'btn btn-sm btn-outline-primary', id: 'generateBtn' });
  genBtn.appendChild(icon('bi bi-robot me-1'));
  genBtn.appendChild(document.createTextNode('Generate'));
  genBtn.addEventListener('click', () => generateDescriptions(seriesId));

  const imgCheck = h('input', { type: 'checkbox', cls: 'form-check-input m-0', id: 'genIncludeImages' });
  const imgLabel = h('label', { cls: 'd-flex align-items-center gap-1 small text-muted', style: 'cursor:pointer' });
  imgLabel.appendChild(imgCheck);
  imgLabel.appendChild(document.createTextNode(' Include images'));

  const headerLabel = h('span', { cls: 'small fw-medium' });
  headerLabel.appendChild(icon('bi bi-robot me-1'));
  headerLabel.appendChild(document.createTextNode('AI Generation'));

  return h('div', { cls: 'card mb-3' },
    h('div', { cls: 'card-header py-2' }, headerLabel),
    h('div', { cls: 'card-body p-2' },
      h('div', { cls: 'd-flex gap-2 flex-wrap align-items-end' },
        h('div', { cls: 'flex-grow-1' }, h('label', { cls: 'form-label small mb-0', text: 'Hint' }), hintInput),
        h('div', null, h('label', { cls: 'form-label small mb-0', text: 'Provider' }), provSel),
        h('div', null, h('label', { cls: 'form-label small mb-0', text: 'Model' }), modelSel),
        h('div', null, h('label', { cls: 'form-label small mb-0 d-block', text: ' ' }), genBtn),
        h('div', { cls: 'align-self-end pb-1' }, imgLabel))));
}

async function generateDescriptions(seriesId) {
  const btn = document.getElementById('generateBtn');
  const provider = document.getElementById('genProvider')?.value || null;
  const model    = document.getElementById('genModel')?.value.trim() || null;
  const hint          = document.getElementById('genHint')?.value.trim() || null;
  const includeImages = document.getElementById('genIncludeImages')?.checked ?? false;
  if (btn) {
    btn.disabled = true;
    btn.replaceChildren(h('span', { cls: 'spinner-border spinner-border-sm me-1' }), document.createTextNode('Generating…'));
  }
  try {
    const newVariants = await apiFetch('POST', '/api/series/' + seriesId + '/generate', {
      provider: provider || null, model: model || null, hint: hint || null, include_images: includeImages,
    });
    await loadSeriesDetail(seriesId);
    applyVariant(0);
    const cost = newVariants[0]?.cost_usd;
    const costLabel = cost > 0 ? ` · $${cost.toFixed(4)}` : '';
    showToast(`Generated new variants${costLabel}`, 'success');
  } catch (e) {
    showToast(e.message, 'danger');
    if (btn) {
      btn.disabled = false;
      btn.replaceChildren(icon('bi bi-robot me-1'), document.createTextNode('Generate'));
    }
  }
}

// ── Actions card ──────────────────────────────────────────────────────────────
function buildActionsCard(series) {
  const statusSel = document.createElement('select');
  statusSel.className = 'form-select form-select-sm'; statusSel.id = 'statusSelect'; statusSel.style.width = '140px';
  ['new','draft','approved','scheduled','partial_posted','posted','skip'].forEach(s => {
    const o = document.createElement('option'); o.value = s; o.textContent = s;
    if (s === series.status) o.selected = true;
    statusSel.appendChild(o);
  });
  const saveStatusBtn = h('button', { cls: 'btn btn-sm btn-outline-primary' });
  saveStatusBtn.appendChild(icon('bi bi-floppy me-1'));
  saveStatusBtn.appendChild(document.createTextNode('Save status'));
  saveStatusBtn.addEventListener('click', () => saveStatus(series.id));

  const mkPostBtn = (label, platform, iconCls, btnCls) => {
    const btn = h('button', { cls: 'btn btn-sm ' + btnCls });
    btn.appendChild(icon(iconCls + ' me-1'));
    btn.appendChild(document.createTextNode(label));
    btn.addEventListener('click', () => postNow(series.id, platform));
    return btn;
  };

  const dateInput = h('input', { type: 'datetime-local', cls: 'form-control form-control-sm', id: 'schedDate', style: 'width:200px' });
  if (series.scheduled_at) {
    const d = new Date(series.scheduled_at.endsWith('Z') ? series.scheduled_at : series.scheduled_at + 'Z');
    dateInput.value = d.toISOString().slice(0, 16);
  }
  const tgCheck = h('input', { type: 'checkbox', cls: 'form-check-input m-0', id: 'schedTg' });
  if ((series.scheduled_targets || []).includes('telegram')) tgCheck.checked = true;
  const igCheck = h('input', { type: 'checkbox', cls: 'form-check-input m-0', id: 'schedIg' });
  if ((series.scheduled_targets || []).includes('instagram')) igCheck.checked = true;

  const schedBtn = h('button', { cls: 'btn btn-sm btn-outline-primary' });
  schedBtn.appendChild(icon('bi bi-calendar-plus me-1'));
  schedBtn.appendChild(document.createTextNode('Schedule'));
  schedBtn.addEventListener('click', () => scheduleSeries(series.id));

  const schedControls = h('div', { cls: 'd-flex gap-2 flex-wrap align-items-center' },
    dateInput,
    h('label', { cls: 'd-flex align-items-center gap-1 small' }, tgCheck, document.createTextNode(' TG')),
    h('label', { cls: 'd-flex align-items-center gap-1 small' }, igCheck, document.createTextNode(' IG')),
    schedBtn);

  if (series.status === 'scheduled') {
    const cancelBtn = h('button', { cls: 'btn btn-sm btn-outline-warning' });
    cancelBtn.appendChild(icon('bi bi-x-circle me-1'));
    cancelBtn.appendChild(document.createTextNode('Cancel'));
    cancelBtn.addEventListener('click', () => cancelSchedule(series.id));
    schedControls.appendChild(cancelBtn);
  }

  const headerLabel = h('span', { cls: 'small fw-medium' });
  headerLabel.appendChild(icon('bi bi-send me-1'));
  headerLabel.appendChild(document.createTextNode('Actions'));

  const deleteSeriesBtn = h('button', {
    cls: 'btn btn-xs btn-outline-danger ms-auto',
    title: 'Delete series',
  });
  deleteSeriesBtn.appendChild(icon('bi bi-trash'));
  deleteSeriesBtn.addEventListener('click', () => deleteSeries(series.id));

  return h('div', { cls: 'card mb-3' },
    h('div', { cls: 'card-header d-flex align-items-center py-2' }, headerLabel, deleteSeriesBtn),
    h('div', { cls: 'card-body p-2' },
      h('div', { cls: 'd-flex gap-2 align-items-center mb-3' }, statusSel, saveStatusBtn),
      h('div', { cls: 'mb-3' },
        h('div', { cls: 'small text-muted mb-1 fw-medium', text: 'Post now' }),
        h('div', { cls: 'd-flex gap-2 flex-wrap' },
          mkPostBtn('Telegram',  'telegram',  'bi bi-telegram',  'btn-outline-info'),
          mkPostBtn('Instagram & FB Page', 'instagram', 'bi bi-instagram', 'btn-outline-danger'),
          mkPostBtn('Both',      'both',      'bi bi-send',      'btn-outline-secondary'))),
      h('div', null,
        h('div', { cls: 'small text-muted mb-1 fw-medium', text: 'Schedule' }),
        schedControls,
        h('div', { id: 'schedResult', cls: 'mt-1 small' }))));
}

async function saveStatus(seriesId) {
  const status = document.getElementById('statusSelect')?.value;
  try {
    const updated = await apiFetch('PUT', '/api/series/' + seriesId, { status });
    App.currentSeries = updated;
    updateSeriesItem(updated);
    showToast('Status saved', 'success');
  } catch (e) { showToast(e.message, 'danger'); }
}

async function deleteSeries(seriesId) {
  try {
    await apiFetch('DELETE', '/api/series/' + seriesId);
    App.series = App.series.filter(s => s.id !== seriesId);
    App.currentSeriesId = null;
    App.currentSeries = null;
    document.getElementById('si-' + seriesId)?.remove();
    document.getElementById('editorPanel').replaceChildren(
      h('p', { cls: 'text-muted text-center mt-5 d-none d-lg-block', text: 'Select a series to edit' })
    );
    showToast('Moved to Trash', 'success');
  } catch (e) { showToast(e.message, 'danger'); }
}

// ── Draft restore ─────────────────────────────────────────────────────────────
function restoreDraft(seriesId) {
  const raw = localStorage.getItem('draft_' + seriesId);
  if (!raw) return;
  try {
    const d = JSON.parse(raw);
    if (!App.currentSeries?.description_en && d.desc_en) {
      const set = (id, v) => { const el = document.getElementById(id); if (el) el.value = v || ''; };
      set('editorTitle', d.title); set('f_desc_en', d.desc_en); set('f_desc_ru', d.desc_ru);
      set('f_tags_ig', d.tags_ig); set('f_tags_tg', d.tags_tg);
    }
  } catch (_) {}
}
