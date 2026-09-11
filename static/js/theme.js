try {
  const preference = localStorage.getItem('portal-theme');
  if (preference === 'light' || preference === 'dark') document.documentElement.dataset.theme = preference;
} catch { /* Keep the organization default when storage is unavailable. */ }
