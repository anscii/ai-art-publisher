// ── Editor entry point ────────────────────────────────────────────────────────
function renderEditor(series) {
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

  const headerLabel = h('span', { cls: 'small fw-medium' });
  headerLabel.appendChild(icon('bi bi-images me-1'));
  const queuedCount = series.images.filter(i => i.status === 'queued').length;
  const countLabel = queuedCount > 0
    ? 'Images (' + queuedCount + ' queued / ' + series.images.length + ')'
    : 'Images (' + series.images.length + ')';
  headerLabel.appendChild(document.createTextNode(countLabel));

  const strip = h('div', { id: 'imageStrip', cls: 'd-flex gap-2', style: 'min-height:80px;overflow-x:auto;flex-wrap:nowrap;padding-bottom:4px' });
  if (!series.images.length) {
    strip.appendChild(h('span', { cls: 'text-muted small align-self-center p-2', text: 'No images yet' }));
  } else {
    series.images.forEach(img => strip.appendChild(buildThumb(img, series.id)));
  }

  return h('div', { cls: 'card mb-3' },
    h('div', { cls: 'card-header d-flex justify-content-between align-items-center py-2' }, headerLabel, addBtn),
    h('div', { cls: 'card-body p-2' }, strip));
}

function buildThumb(img, seriesId) {
  const imgEl = document.createElement('img');
  imgEl.setAttribute('src', img.public_url);
  imgEl.className = 'rounded';
  imgEl.style.cssText = 'width:80px;height:70px;object-fit:cover';
  imgEl.loading = 'lazy';
  imgEl.style.cursor = 'zoom-in';
  imgEl.addEventListener('click', e => {
    e.stopPropagation();
    const strip = document.getElementById('imageStrip');
    const thumbs = [...strip.querySelectorAll('[data-image-id]')];
    const images = thumbs.map(el => ({
      id: el.dataset.imageId,
      public_url: el.querySelector('img').getAttribute('src'),
    }));
    const idx = thumbs.findIndex(el => el.dataset.imageId === img.id);
    openLightbox(images, idx >= 0 ? idx : 0);
  });

  const menuBtn = h('button', { cls: 'btn btn-xs btn-dark opacity-75', text: '⋯' });
  menuBtn.setAttribute('data-bs-toggle', 'dropdown');
  menuBtn.addEventListener('click', e => e.stopPropagation());

  const dropItems = document.createElement('ul');
  dropItems.className = 'dropdown-menu dropdown-menu-end';

  const movable = App.series.filter(s => s.id !== seriesId).slice(0, 15);
  if (movable.length) {
    const hdr = document.createElement('li');
    hdr.appendChild(h('h6', { cls: 'dropdown-header', text: 'Move to' }));
    dropItems.appendChild(hdr);
    movable.forEach(s => {
      const li = document.createElement('li');
      const a = h('a', { cls: 'dropdown-item small', href: '#', text: s.title || s.original_folder_name || s.id.slice(0,8) });
      a.addEventListener('click', e => { e.preventDefault(); moveImage(img.id, s.id, seriesId); });
      li.appendChild(a);
      dropItems.appendChild(li);
    });
    const divLi = document.createElement('li');
    divLi.appendChild(h('hr', { cls: 'dropdown-divider' }));
    dropItems.appendChild(divLi);
  }

  const delLi = document.createElement('li');
  const delA = h('a', { cls: 'dropdown-item small text-danger', href: '#' });
  delA.appendChild(icon('bi bi-trash me-1'));
  delA.appendChild(document.createTextNode('Delete'));
  delA.addEventListener('click', e => { e.preventDefault(); deleteImage(img.id, seriesId); });
  delLi.appendChild(delA);
  dropItems.appendChild(delLi);

  const gripEl = h('div', { cls: 'thumb-grip position-absolute' });
  gripEl.appendChild(icon('bi bi-grip-vertical'));

  const statusBtn = h('button', {
    cls: 'btn btn-xs position-absolute top-0 start-0 m-1 p-0 border-0 bg-transparent',
    style: 'line-height:1',
  });
  statusBtn.appendChild(icon(_statusIcon(img.status)));
  statusBtn.addEventListener('click', async e => {
    e.stopPropagation();
    const next = img.status === 'queued' ? 'pending' : 'queued';
    try {
      const updated = await apiFetch('PATCH', '/api/images/' + img.id + '/status', { status: next });
      App.currentSeries = updated;
      renderEditor(updated);
    } catch (err) { showToast(err.message, 'danger'); }
  });

  const outerCls = 'position-relative flex-shrink-0' + (img.status === 'posted' ? ' thumb-posted' : '');
  return h('div', { cls: outerCls, 'data-image-id': img.id },
    imgEl,
    statusBtn,
    gripEl,
    h('div', { cls: 'position-absolute top-0 end-0 m-1' },
      h('div', { cls: 'dropdown' }, menuBtn, dropItems)));
}

function _statusIcon(status) {
  if (status === 'queued') return 'bi bi-check-circle-fill text-primary';
  if (status === 'posted') return 'bi bi-check-circle-fill text-success';
  if (status === 'skip')   return 'bi bi-x-circle-fill text-secondary';
  return 'bi bi-circle text-white';
}

let _sortable = null;
let _lightboxImages = [];
let _lightboxIdx    = 0;
let _lightboxOpen   = false;

function initImageSortable(seriesId) {
  const strip = document.getElementById('imageStrip');
  if (!strip) return;
  if (_sortable) { _sortable.destroy(); _sortable = null; }
  _sortable = Sortable.create(strip, {
    animation: 150,
    ghostClass: 'sortable-ghost',
    handle: '.thumb-grip',
    touchStartThreshold: 4,
    onEnd: async () => {
      const ids = [...strip.querySelectorAll('[data-image-id]')].map(el => el.dataset.imageId);
      try {
        await apiFetch('PUT', '/api/series/' + seriesId + '/images/reorder', { image_ids: ids });
      } catch (e) { showToast('Reorder failed: ' + e.message, 'danger'); }
    },
  });
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
}

function lightboxNav(delta) {
  _lightboxIdx = (_lightboxIdx + delta + _lightboxImages.length) % _lightboxImages.length;
  _lightboxRender();
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
      showToast('Images uploaded', 'success');
    } catch (e) { showToast(e.message, 'danger'); }
  });
  input.click();
}

async function moveImage(imageId, targetId, currentId) {
  try {
    await apiFetch('PUT', '/api/images/' + imageId + '/move', { target_series_id: targetId });
    await loadSeriesDetail(currentId);
    const t = await apiFetch('GET', '/api/series/' + targetId);
    updateSeriesItem(t);
    showToast('Image moved', 'success');
  } catch (e) { showToast(e.message, 'danger'); }
}

async function deleteImage(imageId, seriesId) {
  showConfirm('Delete this image?', async () => {
    try {
      await apiFetch('DELETE', '/api/images/' + imageId);
      await loadSeriesDetail(seriesId);
      showToast('Deleted', 'success');
    } catch (e) { showToast(e.message, 'danger'); }
  });
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
      variantBtns.appendChild(btn);
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
    mkField('Description EN (Instagram)', descEn),
    mkField('Description RU (Telegram)', descRu),
    mkField('Instagram tags', tagsIg),
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
  const modelInput = h('input', { type: 'text', cls: 'form-control form-control-sm', id: 'genModel', placeholder: 'default', style: 'width:150px' });
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
        h('div', null, h('label', { cls: 'form-label small mb-0', text: 'Model' }), modelInput),
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
    await apiFetch('POST', '/api/series/' + seriesId + '/generate', {
      provider: provider || null, model: model || null, hint: hint || null, include_images: includeImages,
    });
    await loadSeriesDetail(seriesId);
    showToast('Generated 3 new variants', 'success');
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
  const saveStatusBtn = h('button', { cls: 'btn btn-sm btn-outline-secondary' });
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

  return h('div', { cls: 'card mb-3' },
    h('div', { cls: 'card-header py-2' }, headerLabel),
    h('div', { cls: 'card-body p-2' },
      h('div', { cls: 'd-flex gap-2 align-items-center mb-3' }, statusSel, saveStatusBtn),
      h('div', { cls: 'mb-3' },
        h('div', { cls: 'small text-muted mb-1 fw-medium', text: 'Post now' }),
        h('div', { cls: 'd-flex gap-2 flex-wrap' },
          mkPostBtn('Telegram',  'telegram',  'bi bi-telegram',  'btn-outline-info'),
          mkPostBtn('Instagram', 'instagram', 'bi bi-instagram', 'btn-outline-danger'),
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
