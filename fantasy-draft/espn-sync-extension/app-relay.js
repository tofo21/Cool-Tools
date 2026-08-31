(() => {
  "use strict";
  const STORAGE_KEY = "draftCommandEspnSnapshot";
  const CONTROL_KEY = "draftCommandEspnControl";

  function bridgeToken() {
    try { return crypto.randomUUID(); } catch (_) { return `${Date.now()}-${Math.random().toString(16).slice(2)}`; }
  }

  function post(type, snapshot = null, control = null) {
    const details = {
      connected: true,
      paused: Boolean(control?.paused),
      pickCount: Number(snapshot?.picks?.length || 0),
      detectedBy: snapshot?.detectedBy || null,
      espnUrl: snapshot?.espnUrl || null,
      relayedAt: snapshot?.relayedAt || null,
      controlUpdatedAt: control?.updatedAt || null,
      resetToken: control?.resetToken || null,
    };
    window.postMessage({
      source: "draft-command-espn-bridge",
      type,
      details,
      snapshot: type === "ESPN_PICKS" ? snapshot : null,
    }, window.location.origin);
  }

  function publishStored() {
    chrome.storage.local.get([STORAGE_KEY, CONTROL_KEY], (result) => {
      const snapshot = result[STORAGE_KEY] || null;
      const control = result[CONTROL_KEY] || null;
      if (control?.paused) {
        post("ESPN_BRIDGE_STATUS", null, control);
      } else {
        post(snapshot?.picks ? "ESPN_PICKS" : "ESPN_BRIDGE_STATUS", snapshot, control);
      }
    });
  }

  function clearBridge() {
    const control = {
      paused: true,
      resetToken: bridgeToken(),
      updatedAt: new Date().toISOString(),
    };
    chrome.storage.local.set({ [CONTROL_KEY]: control }, () => {
      chrome.storage.local.remove(STORAGE_KEY, () => post("ESPN_BRIDGE_CLEARED", null, control));
    });
  }

  function resumeBridge() {
    const control = {
      paused: false,
      resetToken: bridgeToken(),
      updatedAt: new Date().toISOString(),
    };
    chrome.storage.local.remove(STORAGE_KEY, () => {
      chrome.storage.local.set({ [CONTROL_KEY]: control }, () => post("ESPN_BRIDGE_RESUMED", null, control));
    });
  }

  chrome.storage.onChanged.addListener((changes, areaName) => {
    if (areaName === "local" && (changes[STORAGE_KEY] || changes[CONTROL_KEY])) publishStored();
  });
  window.addEventListener("message", (event) => {
    if (event.source !== window || event.origin !== window.location.origin || event.data?.source !== "draft-command-app") return;
    if (event.data.type === "ESPN_BRIDGE_PING") publishStored();
    if (event.data.type === "ESPN_BRIDGE_CLEAR") clearBridge();
    if (event.data.type === "ESPN_BRIDGE_RESUME") resumeBridge();
  });

  publishStored();
  setInterval(publishStored, 5000);
})();
