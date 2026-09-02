// Shared dashboard helpers.
(function () {
  'use strict';

  const fmtRisk = (r) => (Math.round((r || 0) * 100)) + '%';

  // Fetch JSON with error handling.
  window.apiGet = async function (url) {
    const res = await fetch(url);
    if (!res.ok) throw new Error('API ' + url + ' failed: ' + res.status);
    return res.json();
  };

  window.fmtRisk = fmtRisk;
})();
