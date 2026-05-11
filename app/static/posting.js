async function postNow(seriesId, platform) {
  const label = { telegram: 'Telegram', instagram: 'Instagram', both: 'both' }[platform] || platform;
  showConfirm('Post to ' + label + '?', async () => {
    try {
      await apiFetch('PUT', '/api/series/' + seriesId + '/queue', { image_ids: [..._selectedImages] });
      const result = await apiFetch('POST', '/api/series/' + seriesId + '/post/' + platform);
      if (result.success) {
        showToast(result.message, 'success');
        const updated = await apiFetch('GET', '/api/series/' + seriesId);
        App.currentSeries = updated;
        updateSeriesItem(updated);
      } else {
        showToast('Error: ' + result.message, 'danger');
      }
    } catch (e) { showToast(e.message, 'danger'); }
  });
}

async function scheduleSeries(seriesId) {
  const dateVal = document.getElementById('schedDate')?.value;
  if (!dateVal) { showToast('Please select a date and time', 'danger'); return; }
  const targets = [];
  if (document.getElementById('schedTg')?.checked) targets.push('telegram');
  if (document.getElementById('schedIg')?.checked) targets.push('instagram');
  if (!targets.length) { showToast('Select at least one platform', 'danger'); return; }
  try {
    await apiFetch('PUT', '/api/series/' + seriesId + '/queue', { image_ids: [..._selectedImages] });
    await apiFetch('POST', '/api/series/' + seriesId + '/schedule', {
      datetime_utc: new Date(dateVal).toISOString(),
      targets,
    });
    const resultEl = document.getElementById('schedResult');
    if (resultEl) {
      resultEl.replaceChildren(h('span', { cls: 'text-success', text: '✅ Scheduled for ' + dateVal + ' UTC' }));
    }
    const updated = await apiFetch('GET', '/api/series/' + seriesId);
    App.currentSeries = updated;
    updateSeriesItem(updated);
    showToast('Scheduled', 'success');
  } catch (e) { showToast(e.message, 'danger'); }
}

async function cancelSchedule(seriesId) {
  showConfirm('Cancel this scheduled post?', async () => {
    try {
      await apiFetch('DELETE', '/api/series/' + seriesId + '/schedule');
      const updated = await apiFetch('GET', '/api/series/' + seriesId);
      App.currentSeries = updated;
      updateSeriesItem(updated);
      await loadSeriesDetail(seriesId);
      showToast('Schedule cancelled', 'success');
    } catch (e) { showToast(e.message, 'danger'); }
  });
}
