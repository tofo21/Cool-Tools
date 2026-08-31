(() => {
  "use strict";
  const STORAGE_KEY = "draftCommandEspnSnapshot";
  const CONTROL_KEY = "draftCommandEspnControl";
  const STATE_EVENT = "draft-command-espn-state";
  const CONTROL_EVENT = "draft-command-espn-control";
  let paused = true;

  function publishControl(control) {
    paused = Boolean(control?.paused);
    window.dispatchEvent(new CustomEvent(CONTROL_EVENT, {
      detail: {
        paused,
        resetToken: control?.resetToken || null,
        updatedAt: control?.updatedAt || null,
      },
    }));
  }

  window.addEventListener(STATE_EVENT, (event) => {
    if (paused) return;
    try {
      const snapshot = JSON.parse(JSON.stringify(event.detail || {}));
      snapshot.relayedAt = Date.now();
      chrome.storage.local.set({ [STORAGE_KEY]: snapshot });
    } catch (_) { /* ignore non-serializable ESPN payload fragments */ }
  });

  chrome.storage.onChanged.addListener((changes, areaName) => {
    if (areaName === "local" && changes[CONTROL_KEY]) publishControl(changes[CONTROL_KEY].newValue || null);
  });

  chrome.storage.local.get(CONTROL_KEY, (result) => publishControl(result[CONTROL_KEY] || null));
})();
