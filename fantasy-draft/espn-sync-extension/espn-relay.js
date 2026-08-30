(() => {
  "use strict";
  const STORAGE_KEY = "draftCommandEspnSnapshot";

  window.addEventListener("draft-command-espn-state", (event) => {
    try {
      const snapshot = JSON.parse(JSON.stringify(event.detail || {}));
      snapshot.relayedAt = Date.now();
      chrome.storage.local.set({ [STORAGE_KEY]: snapshot });
    } catch (_) { /* ignore non-serializable ESPN payload fragments */ }
  });
})();
