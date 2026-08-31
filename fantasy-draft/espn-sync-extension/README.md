# Draft Command ESPN Sync

This private Chromium extension moves ESPN draft-room pick data between two tabs on the same computer:

- the ESPN fantasy football draft room;
- Tony's Draft Command page.

It does not collect passwords, cookies, browsing history, or data from unrelated sites. Draft snapshots remain in the browser's local extension storage and are not sent to a separate server.

## Install or replace in Chrome or Edge

1. In Draft Command, run **Hard Reset Draft**, then close the old ESPN draft-room tab.
2. Download the new `espn-sync-extension.zip` and extract it to a new folder.
3. Open `chrome://extensions` (or `edge://extensions`) and turn on **Developer mode**.
4. Remove the old **Draft Command ESPN Sync** extension. An unpacked extension does not update itself.
5. Choose **Load unpacked** and select the newly extracted `espn-sync-extension` folder that directly contains `manifest.json`.
6. Confirm the extension card reports version **0.3.0**.
7. Reload Draft Command with `Ctrl+Shift+R`.
8. Open the intended ESPN draft room, select **Live sync → ESPN**, and choose **Check / resume ESPN**.

## Reset between drafts

**Hard Reset Draft** in Draft Command performs one coordinated reset:

1. clears modeled events, source observations, optional keeper seeds, logs and recovery snapshots;
2. creates a new session ID and bridge generation;
3. clears both extension and ESPN-page caches;
4. pauses the bridge so an old or completed mock cannot repopulate the board;
5. returns Draft Command to Manual mode.

Close the prior ESPN room. When the intended room is open, select **ESPN** or choose **Check / resume ESPN** to resume the bridge from a fresh snapshot.

After a reset, open the intended ESPN room and choose **Check / resume ESPN**. Reusing the same ESPN URL is supported because the new generation forces a fresh in-page scan.

Bridge version: **0.3.0**.

Manual draft entry remains available if ESPN changes its draft-room internals.
