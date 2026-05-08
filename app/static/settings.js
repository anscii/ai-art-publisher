async function loadSettings() {
  try {
    const s = await apiFetch('GET', '/api/settings');
    const fields = [
      'anthropic_api_key','openai_api_key','google_api_key','default_model',
      'telegram_bot_token','telegram_channel_id','instagram_access_token','instagram_user_id',
      'r2_endpoint','r2_access_key','r2_secret_key','r2_bucket','r2_public_base_url',
    ];
    fields.forEach(f => { const el = document.getElementById('s_' + f); if (el) el.value = s[f] || ''; });
    const provEl = document.getElementById('s_default_provider');
    if (provEl && s.default_provider) provEl.value = s.default_provider;
  } catch (e) { showToast('Failed to load settings: ' + e.message, 'danger'); }
}

async function saveSettings() {
  const fields = [
    'anthropic_api_key','openai_api_key','google_api_key','default_provider','default_model',
    'telegram_bot_token','telegram_channel_id','instagram_access_token','instagram_user_id',
    'r2_endpoint','r2_access_key','r2_secret_key','r2_bucket','r2_public_base_url',
  ];
  const body = {};
  fields.forEach(f => {
    const el = document.getElementById('s_' + f);
    if (!el) return;
    const val = el.value.trim();
    if (val && val !== '****') body[f] = val;
  });
  try {
    await apiFetch('PUT', '/api/settings', body);
    showToast('Settings saved', 'success');
  } catch (e) { showToast(e.message, 'danger'); }
}

function togglePass(btn) {
  const input = btn.previousElementSibling;
  if (input.type === 'password') {
    input.type = 'text';
    btn.replaceChildren(icon('bi bi-eye-slash'));
  } else {
    input.type = 'password';
    btn.replaceChildren(icon('bi bi-eye'));
  }
}

async function testConn(service, btn) {
  const origChildren = [...btn.childNodes].map(n => n.cloneNode(true));
  btn.disabled = true;
  btn.replaceChildren(h('span', { cls: 'spinner-border spinner-border-sm' }));
  try {
    const result = await apiFetch('POST', '/api/settings/test/' + service);
    const cls = result.ok ? 'btn-outline-success' : 'btn-outline-danger';
    btn.classList.replace('btn-outline-secondary', cls);
    showToast(result.message, result.ok ? 'success' : 'danger');
    setTimeout(() => btn.classList.replace(cls, 'btn-outline-secondary'), 3000);
  } catch (e) { showToast(e.message, 'danger'); }
  finally {
    btn.disabled = false;
    btn.replaceChildren(...origChildren);
  }
}
