"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const root = path.resolve(__dirname, "..");
const read = (file) => fs.readFileSync(path.join(root, file), "utf8");

function eventEnvironment(initial = {}) {
  const data = { ...initial };
  const windowListeners = {};
  const storageListeners = [];
  const posted = [];

  const window = {
    location: { origin: "https://tofo21.github.io" },
    addEventListener(type, listener) {
      (windowListeners[type] ||= []).push(listener);
    },
    postMessage(message) {
      posted.push(message);
    },
    dispatchEvent(event) {
      for (const listener of windowListeners[event.type] || []) listener(event);
    },
  };

  function emitStorage(changes) {
    for (const listener of storageListeners) listener(changes, "local");
  }

  const chrome = {
    storage: {
      local: {
        get(keys, callback) {
          const requested = Array.isArray(keys) ? keys : [keys];
          const result = {};
          for (const key of requested) if (key in data) result[key] = data[key];
          callback(result);
        },
        set(values, callback) {
          const changes = {};
          for (const [key, value] of Object.entries(values)) {
            changes[key] = { oldValue: data[key], newValue: value };
            data[key] = value;
          }
          emitStorage(changes);
          callback?.();
        },
        remove(keys, callback) {
          const requested = Array.isArray(keys) ? keys : [keys];
          const changes = {};
          for (const key of requested) {
            if (key in data) {
              changes[key] = { oldValue: data[key], newValue: undefined };
              delete data[key];
            }
          }
          if (Object.keys(changes).length) emitStorage(changes);
          callback?.();
        },
      },
      onChanged: {
        addListener(listener) {
          storageListeners.push(listener);
        },
      },
    },
  };

  return {
    chrome,
    data,
    posted,
    window,
    sendMessage(message) {
      for (const listener of windowListeners.message || []) {
        listener({ type: "message", source: window, origin: window.location.origin, data: message });
      }
    },
  };
}

const appRelay = eventEnvironment({
  draftCommandEspnSnapshot: { picks: [{ overall: 1 }], detectedBy: "fixture" },
});
vm.runInNewContext(read("espn-sync-extension/app-relay.js"), {
  window: appRelay.window,
  chrome: appRelay.chrome,
  crypto: { randomUUID: () => "fixture-token" },
  Date,
  Math,
  setInterval() { return 1; },
});
assert.equal(appRelay.posted.at(-1).type, "ESPN_PICKS");

appRelay.sendMessage({ source: "draft-command-app", type: "ESPN_BRIDGE_CLEAR" });
assert.equal(appRelay.data.draftCommandEspnSnapshot, undefined);
assert.equal(appRelay.data.draftCommandEspnControl.paused, true);
assert.ok(appRelay.posted.some((message) => message.type === "ESPN_BRIDGE_CLEARED"));

appRelay.sendMessage({ source: "draft-command-app", type: "ESPN_BRIDGE_RESUME" });
assert.equal(appRelay.data.draftCommandEspnSnapshot, undefined);
assert.equal(appRelay.data.draftCommandEspnControl.paused, false);
assert.ok(appRelay.posted.some((message) => message.type === "ESPN_BRIDGE_RESUMED"));

class CustomEvent {
  constructor(type, options = {}) {
    this.type = type;
    this.detail = options.detail;
  }
}

const espnRelay = eventEnvironment({
  draftCommandEspnControl: { paused: true, resetToken: "reset-1" },
});
vm.runInNewContext(read("espn-sync-extension/espn-relay.js"), {
  window: espnRelay.window,
  chrome: espnRelay.chrome,
  CustomEvent,
  Date,
});
espnRelay.window.dispatchEvent(new CustomEvent("draft-command-espn-state", {
  detail: { picks: [{ overall: 1 }] },
}));
assert.equal(espnRelay.data.draftCommandEspnSnapshot, undefined, "paused bridge must reject stale snapshots");

espnRelay.chrome.storage.local.set({
  draftCommandEspnControl: { paused: false, resetToken: "reset-2" },
});
espnRelay.window.dispatchEvent(new CustomEvent("draft-command-espn-state", {
  detail: { picks: [{ overall: 1 }] },
}));
assert.equal(espnRelay.data.draftCommandEspnSnapshot.picks.length, 1, "resumed bridge should accept fresh snapshots");

const appSource = read("app.js");
const syncSource = read("sync.js");
const index = read("index.html");
const manifest = JSON.parse(read("espn-sync-extension/manifest.json"));
const zip = fs.readFileSync(path.join(root, "espn-sync-extension.zip"));

assert.match(appSource, /draft-command-reset-live-picks/);
assert.match(syncSource, /ESPN_BRIDGE_CLEAR/);
assert.match(syncSource, /ESPN_BRIDGE_RESUME/);
assert.match(syncSource, /window\.DraftCommandSync/);
assert.match(index, /id="espnClearBridge"/);
assert.equal(manifest.version, "0.2.0");
assert.ok(zip.includes(Buffer.from('"version": "0.2.0"')), "downloadable ZIP should contain bridge v0.2.0");
assert.match(read("espn-sync-extension/espn-main.js"), /if \(paused\) return;/);

console.log("ESPN sync reset tests passed");
