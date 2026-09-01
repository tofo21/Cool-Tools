#!/usr/bin/env node
"use strict";

const crypto = require("node:crypto");
const fs = require("node:fs");
const path = require("node:path");

const projectRoot = path.resolve(__dirname, "..");
const output = path.join(__dirname, "opponent-intent-runtime-manifest.json");
const artifacts = [
  "data/opponent-intent-package.js",
  "model/opponent-intent.js",
  "model/opponent-intent-worker.js",
  "model/opponent-intent-package.schema.json",
  "model/opponent-intent-integration-contract.json",
  "model/opponent-intent-validation.json"
].map((relativePath) => {
  const bytes = fs.readFileSync(path.join(projectRoot, relativePath));
  return {
    path: relativePath,
    bytes: bytes.length,
    sha256: crypto.createHash("sha256").update(bytes).digest("hex")
  };
});

const manifest = {
  schemaVersion: "1.0.0",
  packageId: "espn-opponent-intent-runtime-2026-08-31",
  modelVersion: "espn_opponent_intent_v1.1_candidate",
  generatedAt: "2026-09-01T00:30:12Z",
  startingProductionCommit: "0a6ea9538f2806413d33ef2bc3a261b21ad7fc62",
  startingOpponentIntentCommit: "cc0dcf158c8902c4f5b5c5761c7fde9c3c0babaf",
  marketLock: {
    snapshotId: "espn_2026_frozen_20260901T003012Z_3379127ab1c0",
    captureTimestampUtc: "2026-09-01T00:30:12Z",
    publicationCommit: "49951ca1d45b92a906f84366a02d40c8c2e07e12",
    snapshotSha256: "e333dfbc3196351ea1b04f6fa8a5525db5903067f38318c8d2a725d6f75bc2a2",
    schemaVersion: "espn-market-2026-v1.1",
    status: "frozen",
    coverage: {
      sourceRows: 500,
      draftCommandMapped: 199,
      draftCommandTotal: 200,
      mappedWithRank: 199,
      mappedWithAdp: 199,
      keepersRepresented: 10,
      keepersTotal: 10,
      unresolvedEspnTop160: 0,
      duplicateInternalPlayerIds: 0,
      duplicateEspnPlayerIds: 0,
      soleNonblockingMiss: 190
    }
  },
  publicAssetPolicy: "No raw drafts, pick-level ledgers, identity crosswalks, credentials, cookies or authenticated ESPN responses.",
  artifacts
};

fs.writeFileSync(output, `${JSON.stringify(manifest, null, 2)}\n`, "utf8");
process.stdout.write(`Wrote ${output} with ${artifacts.length} verified artifacts.\n`);
