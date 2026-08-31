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
  generatedAt: "2026-08-31T23:00:00Z",
  startingProductionCommit: "0a6ea9538f2806413d33ef2bc3a261b21ad7fc62",
  publicAssetPolicy: "No raw drafts, pick-level ledgers, identity crosswalks, credentials, cookies or authenticated ESPN responses.",
  artifacts
};

fs.writeFileSync(output, `${JSON.stringify(manifest, null, 2)}\n`, "utf8");
process.stdout.write(`Wrote ${output} with ${artifacts.length} verified artifacts.\n`);
