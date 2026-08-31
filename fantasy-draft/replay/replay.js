(() => {
  "use strict";

  const els = Object.fromEntries([
    "modelBadge", "modelVersion", "modelCoverage", "sourceName", "sourceStatus", "fileInput", "loadSample",
    "runReplay", "exportReport", "decisionCount", "decisionCoverage", "brierScore", "eceScore",
    "agreementScore", "counterScore", "counterCount", "strategyRows", "calibrationSamples", "calibrationChart",
    "decisionRows", "issueCount", "issuesPanel", "issuesList", "toast",
  ].map((id) => [id, document.getElementById(id)]));

  const adapter = window.DraftModel.createAdapter({
    packageData: window.DRAFT_INTELLIGENCE_PACKAGE,
    players: window.PLAYER_DATA,
    season: 2026,
    leagueProfileId: "espn-keeper-10-ppr-2flex-2026",
    fallbackVersion: "fallback-2026.08.27",
  });
  const engine = window.DraftReplay.createEngine({ players: window.PLAYER_DATA, model: adapter });
  let activeLog = engine.sampleLog("espn");
  let activeReport = null;

  const percent = (value) => value == null ? "—" : `${Math.round(value * 100)}%`;
  const decimal = (value, places = 3) => value == null ? "—" : Number(value).toFixed(places);
  const escapeHtml = (value) => String(value ?? "").replace(/[&<>'"]/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" })[character]);

  function showToast(message) {
    els.toast.textContent = message;
    els.toast.classList.add("show");
    setTimeout(() => els.toast.classList.remove("show"), 1800);
  }

  function renderModelHealth() {
    const health = adapter.health();
    els.modelBadge.textContent = health.label;
    els.modelVersion.textContent = health.modelVersion;
    els.modelCoverage.textContent = `${Math.round(health.coverage * 100)}% player coverage · ${health.sourceCount} source${health.sourceCount === 1 ? "" : "s"}`;
  }

  function renderCalibration(calibration) {
    els.calibrationSamples.textContent = `${calibration.count} samples`;
    els.calibrationChart.innerHTML = calibration.bins.map((bin) => `
      <div class="cal-row">
        <span>${bin.range}</span>
        <div class="cal-bars" title="Predicted ${percent(bin.predicted)} · observed ${percent(bin.observed)}">
          <span class="predicted" style="width:${(bin.predicted || 0) * 100}%"></span>
          <span class="observed" style="width:${(bin.observed || 0) * 100}%"></span>
        </div>
        <span>${bin.count} n</span>
        <span>${bin.observed == null ? "—" : percent(bin.observed)}</span>
      </div>`).join("");
  }

  function renderStrategies(strategies) {
    els.strategyRows.innerHTML = strategies.map((strategy) => `
      <tr>
        <td><strong>${escapeHtml(strategy.label)}</strong></td>
        <td>${strategy.choices}</td>
        <td>${decimal(strategy.meanDraftScore, 1)}</td>
        <td class="${strategy.meanValueGap >= 0 ? "positive" : "negative"}">${strategy.meanValueGap > 0 ? "+" : ""}${decimal(strategy.meanValueGap, 1)}</td>
        <td>${percent(strategy.actualAgreement)}</td>
      </tr>`).join("");
  }

  function counterLabel(decision) {
    if (decision.counterfactual.status === "taken") return `<span class="positive">Taken now</span>`;
    if (decision.counterfactual.status === "pending") return `<span class="muted">Window incomplete</span>`;
    const label = decision.counterfactual.status === "survived" ? "Survived" : "Lost before turn";
    return `<span class="${decision.counterfactual.correct ? "positive" : "negative"}">${label}</span>`;
  }

  function renderDecisions(decisions) {
    els.decisionRows.innerHTML = decisions.length ? decisions.map((decision) => `
      <tr>
        <td><strong>${decision.pick}</strong></td>
        <td>${escapeHtml(decision.actual.name)} <span class="muted">${decision.actual.pos}</span></td>
        <td class="${decision.agreed ? "positive" : ""}">${escapeHtml(decision.recommendation?.name || "—")} <span class="muted">${decision.recommendation?.pos || ""}</span></td>
        <td><span class="tag">${escapeHtml(decision.recommendation?.tag || "—")}</span></td>
        <td>${percent(decision.recommendation?.survival)} <span class="muted">to ${decision.nextTonyPick}</span></td>
        <td>${counterLabel(decision)}</td>
      </tr>`).join("") : `<tr><td colspan="6" class="empty">No Tony selections were found in this log.</td></tr>`;
  }

  function renderIssues(issues) {
    els.issueCount.textContent = issues.length ? `${issues.length} import issue${issues.length === 1 ? "" : "s"}` : "No import issues";
    els.issuesPanel.hidden = !issues.length;
    els.issuesList.innerHTML = issues.map((issue) => `<div class="issue"><strong>${escapeHtml(issue.code)}</strong><span>${issue.overall ? `Pick ${issue.overall} · ` : ""}${escapeHtml(issue.playerName || "")}${issue.playerName ? " — " : ""}${escapeHtml(issue.message)}</span></div>`).join("");
  }

  function renderReport(report) {
    const summary = report.summary;
    els.decisionCount.textContent = summary.decisions;
    els.decisionCoverage.textContent = `Log complete through ${summary.completeThroughLabel}`;
    els.brierScore.textContent = decimal(summary.individualCalibration.brier);
    els.eceScore.textContent = percent(summary.individualCalibration.ece);
    els.agreementScore.textContent = percent(summary.recommendationAgreement);
    els.counterScore.textContent = percent(summary.counterfactualAccuracy);
    els.counterCount.textContent = `${summary.counterfactualCount} completed counterfactual${summary.counterfactualCount === 1 ? "" : "s"}`;
    renderStrategies(report.strategies);
    renderCalibration(summary.individualCalibration);
    renderDecisions(report.decisions);
    renderIssues(report.normalized.issues);
    els.exportReport.disabled = false;
  }

  function runReplay() {
    activeReport = engine.run(activeLog);
    if (!activeReport.ok) {
      renderIssues(activeReport.normalized.issues);
      showToast("Replay could not run");
      return;
    }
    renderReport(activeReport);
    showToast(`${activeReport.summary.decisions} decisions replayed`);
  }

  function loadSample() {
    activeLog = engine.sampleLog("espn");
    activeReport = null;
    els.sourceName.textContent = activeLog.name;
    els.sourceStatus.textContent = "A complete 160-slot deterministic test draft is loaded. It exercises all 15 open Tony decisions while preserving his round-16 keeper.";
    els.fileInput.value = "";
    els.exportReport.disabled = true;
    runReplay();
  }

  async function importFile(file) {
    try {
      const parsed = JSON.parse(await file.text());
      const preview = engine.normalizeLog(parsed);
      activeLog = parsed;
      activeReport = null;
      els.sourceName.textContent = file.name;
      els.sourceStatus.textContent = `${preview.events.length} usable events detected · ${preview.platform.toUpperCase()} price layer · ${preview.issues.length} normalization issue${preview.issues.length === 1 ? "" : "s"}.`;
      els.exportReport.disabled = true;
      renderIssues(preview.issues);
      showToast("Draft log loaded");
    } catch (error) {
      showToast("Invalid JSON file");
      els.sourceStatus.textContent = error.message || "The selected file could not be read.";
    }
  }

  function exportReport() {
    if (!activeReport) return;
    const blob = new Blob([JSON.stringify(activeReport, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `draft-command-replay-${new Date().toISOString().slice(0, 10)}.json`;
    link.click();
    URL.revokeObjectURL(url);
  }

  els.fileInput.addEventListener("change", () => { if (els.fileInput.files?.[0]) importFile(els.fileInput.files[0]); });
  els.loadSample.addEventListener("click", loadSample);
  els.runReplay.addEventListener("click", runReplay);
  els.exportReport.addEventListener("click", exportReport);

  renderModelHealth();
  loadSample();
})();
