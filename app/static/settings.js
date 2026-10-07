// Secret field IDs that have a corresponding Test button in their .aap-secret-row.
// (s_r2_access_key is excluded — that row has no Test button, only eye toggle.)
const _SECRET_FIELD_IDS = [
  's_anthropic_api_key', 's_openai_api_key', 's_google_api_key',
  's_deepseek_api_key', 's_openrouter_api_key',
  's_telegram_bot_token', 's_instagram_access_token',
  's_facebook_page_access_token', 's_pinterest_access_token',
  's_r2_secret_key',
];

// Returns the Test button for a given secret field ID.
// The last <button> in the .aap-secret-row is always the Test button
// (eye toggle button comes before it).
function _testBtnFor(fieldId) {
  const input = document.getElementById(fieldId);
  if (!input) return null;
  const row = input.closest('.aap-secret-row');
  if (!row) return null;
  const btns = row.querySelectorAll('button');
  return btns.length > 1 ? btns[btns.length - 1] : null;
}

// Set or clear the ok/missing visual state on a Test button.
// configured=true  → green border + "✓ Tested"
// configured=false → red border   + "Test"
function _setTestBtnState(btn, configured) {
  if (!btn) return;
  btn.classList.remove('aap-btn-test-ok', 'aap-btn-test-missing');
  if (configured) {
    btn.classList.add('aap-btn-test-ok');
    btn.textContent = '✓ Tested';
  } else {
    btn.classList.add('aap-btn-test-missing');
    btn.textContent = 'Test';
  }
}

// Per-User AI settings (/api/me/settings) vs instance config (/api/settings, admin only).
const _MY_FIELDS = [
  'anthropic_api_key', 'openai_api_key', 'google_api_key', 'deepseek_api_key', 'openrouter_api_key',
  'default_provider',
  'anthropic_default_model', 'openai_default_model', 'google_default_model',
  'deepseek_default_model', 'openrouter_default_model', 'image_edit_model',
];
const _INSTANCE_FIELDS = [
  'telegram_bot_token', 'telegram_channel_id', 'telegram_api_id',
  'telegram_api_hash', 'telegram_session_string',
  'instagram_access_token', 'instagram_user_id',
  'facebook_page_access_token', 'facebook_page_id',
  'pinterest_access_token', 'pinterest_default_board_id',
  'r2_endpoint', 'r2_access_key', 'r2_secret_key', 'r2_bucket', 'r2_public_base_url',
];
const _AI_PROVIDERS = ['anthropic', 'openai', 'google', 'deepseek', 'openrouter'];

async function loadSettings() {
  try {
    const s = await apiFetch('GET', '/api/me/settings');
    if (App.user?.is_admin) {
      // Only instance fields: /api/settings also has openrouter_api_key (the Default AI Access key),
      // which must not overwrite the user's own key in the My AI block.
      const inst = await apiFetch('GET', '/api/settings');
      _INSTANCE_FIELDS.forEach(f => { s[f] = inst[f]; });
    }
    [..._MY_FIELDS, ..._INSTANCE_FIELDS].forEach(f => {
      const el = document.getElementById('s_' + f);
      if (el && !el.list && el.tagName !== 'SELECT') { el.value = s[f] || ''; el.dataset.loaded = el.value; }
    });
    const provEl = document.getElementById('s_default_provider');
    if (provEl && s.default_provider) provEl.value = s.default_provider;
    // Model fields are <input list=datalist>: fill the datalist, then set the (free-text) value.
    [..._AI_PROVIDERS, 'image_edit'].forEach(p => {
      const input = document.getElementById(p === 'image_edit' ? 's_image_edit_model' : 's_' + p + '_default_model');
      const dl = document.getElementById('dl_' + p);
      if (!input || !dl) return;
      const val = s[p === 'image_edit' ? 'image_edit_model' : p + '_default_model'] || '';
      buildProviderModelSelect(dl, p, { selectedValue: val });
      input.value = val;
    });
    // Initialise Test button states: green if value is '****' (key saved), red if empty.
    _SECRET_FIELD_IDS.forEach(id => {
      const input = document.getElementById(id);
      _setTestBtnState(_testBtnFor(id), !!(input && input.value === '****'));
    });
  } catch (e) { showToast('Failed to load settings: ' + e.message, 'danger'); }
}

function _collect(fields) {
  const body = {};
  fields.forEach(f => {
    const el = document.getElementById('s_' + f);
    if (!el) return;
    const val = el.value.trim();
    if (val && val !== '****') body[f] = val;
    else if (!val && el.dataset.loaded === '****') body[f] = '';  // user cleared a saved secret
  });
  return body;
}

async function saveSettings() {
  try {
    await apiFetch('PUT', '/api/me/settings', _collect(_MY_FIELDS));
    if (App.user?.is_admin) await apiFetch('PUT', '/api/settings', _collect(_INSTANCE_FIELDS));
    showToast('Settings saved', 'success');
  } catch (e) { showToast(e.message, 'danger'); }
}

function togglePass(btn) {
  const input = btn.previousElementSibling;
  if (input.type === 'password') {
    input.type = 'text';
    btn.setAttribute('aria-label', 'Hide password');
    btn.replaceChildren(icon('bi bi-eye-slash'));
  } else {
    input.type = 'password';
    btn.setAttribute('aria-label', 'Show password');
    btn.replaceChildren(icon('bi bi-eye'));
  }
}

async function testConn(service, btn) {
  btn.disabled = true;
  btn.textContent = '…';
  try {
    const result = await apiFetch('POST', (_AI_PROVIDERS.includes(service) ? '/api/me/settings/test/' : '/api/settings/test/') + service);
    _setTestBtnState(btn, result.ok);
    showToast(result.message, result.ok ? 'success' : 'danger');
  } catch (e) {
    _setTestBtnState(btn, false);
    showToast(e.message, 'danger');
  } finally {
    btn.disabled = false;
  }
}
