(() => {
  "use strict";
  const STORAGE_KEY = "draftCommandEspnSnapshot";

  function send(snapshot) {
    const details = {
      connected: true,
      pickCount: Number(snapshot?.picks?.length || 0),
      detectedBy: snapshot?.detectedBy || null,
      espnUrl: snapshot?.espnUrl || null,
      relayedAt: snapshot?.relayedAt || null,
    };
    window.postMessage({
      source: "draft-command-espn-bridge",
      type: snapshot?.picks ? "ESPN_PICKS" : "ESPN_BRIDGE_STATUS",
      details,
      snapshot: snapshot?.picks ? snapshot : null,
    }, window.location.origin);
  }

  function publishStored() {
    chrome.storage.local.get(STORAGE_KEY, (result) => send(result[STORAGE_KEY] || null));
  }

  chrome.storage.onChanged.addListener((changes, areaName) => {
    if (areaName === "local" && changes[STORAGE_KEY]) send(changes[STORAGE_KEY].newValue || null);
  });
  window.addEventListener("message", (event) => {
    if (event.source === window && event.data?.source === "draft-command-app" && event.data?.type === "ESPN_BRIDGE_PING") publishStored();
  });

  publishStored();
  setInterval(publishStored, 5000);
})();
