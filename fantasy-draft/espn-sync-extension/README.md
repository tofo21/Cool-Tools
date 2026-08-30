# Draft Command ESPN Sync

This private Chromium extension moves ESPN draft-room pick data between two tabs on the same computer:

- the ESPN fantasy football draft room;
- Tony's Draft Command page.

It does not collect passwords, cookies, browsing history, or data from unrelated sites. Draft snapshots remain in the browser's local extension storage and are not sent to a separate server.

## Install in Chrome or Edge

1. Unzip `espn-sync-extension.zip`.
2. Open the browser's Extensions page.
3. Turn on **Developer mode**.
4. Choose **Load unpacked**.
5. Select the unzipped `espn-sync-extension` folder containing `manifest.json`.
6. Open the ESPN draft room and Draft Command in the same browser.
7. In Draft Command, select **Live sync → ESPN** and choose **Check connection**.

Manual draft entry remains available if ESPN changes its draft-room internals.
