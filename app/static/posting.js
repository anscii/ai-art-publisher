async function postNow(postId) {
  showConfirm('Post now?', async () => {
    try {
      const result = await apiFetch('POST', '/api/posts/' + postId + '/post');
      showToast(result.success ? result.message : 'Error: ' + result.message, result.success ? 'success' : 'danger');
      if (App.currentSeriesId) await loadSeriesDetail(App.currentSeriesId);
    } catch (e) { showToast(e.message, 'danger'); }
  });
}

async function schedulePost(postId, datetimeUtc) {
  try {
    await apiFetch('POST', '/api/posts/' + postId + '/schedule', { datetime_utc: datetimeUtc });
    showToast('Scheduled', 'success');
    if (App.currentSeriesId) await loadSeriesDetail(App.currentSeriesId);
  } catch (e) { showToast(e.message, 'danger'); }
}

async function cancelPostSchedule(postId) {
  showConfirm('Cancel this scheduled post?', async () => {
    try {
      await apiFetch('DELETE', '/api/posts/' + postId + '/schedule');
      showToast('Schedule cancelled', 'success');
      if (App.currentSeriesId) await loadSeriesDetail(App.currentSeriesId);
    } catch (e) { showToast(e.message, 'danger'); }
  });
}

async function deletePost(postId) {
  showConfirm('Delete this post?', async () => {
    try {
      await apiFetch('DELETE', '/api/posts/' + postId);
      showToast('Post deleted', 'success');
      if (App.currentSeriesId) await loadSeriesDetail(App.currentSeriesId);
    } catch (e) { showToast(e.message, 'danger'); }
  });
}
