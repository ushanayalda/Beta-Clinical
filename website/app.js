"use strict";

const state = {
  index: null,
  currentCase: null,
};

const screen = document.getElementById("screen");
const nav = document.getElementById("caseNavigation");
const sidebar = document.getElementById("sidebar");
const menuButton = document.getElementById("menuButton");

menuButton.addEventListener("click", () => {
  const open = sidebar.classList.toggle("open");
  menuButton.setAttribute("aria-expanded", String(open));
});

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function query() {
  return new URLSearchParams(window.location.search);
}

function caseUrl(caseId, view = "stem") {
  return `?case=${encodeURIComponent(caseId)}&view=${encodeURIComponent(view)}`;
}

function progressKey(caseId) {
  return `clinical-pathway-progress:${caseId}`;
}

function getProgress(caseId) {
  const raw = Number.parseInt(localStorage.getItem(progressKey(caseId)) || "0", 10);
  return Number.isFinite(raw) && raw >= 0 && raw <= 3 ? raw : 0;
}

function setProgress(caseId, value) {
  localStorage.setItem(progressKey(caseId), String(value));
}

function progressControl(data) {
  const levels = data.progress_control.levels;
  const value = getProgress(data.case_id);
  const degrees = `${value * 120}deg`;
  return `
    <div class="progress-wrap">
      <button class="progress-ring" id="progressRing" style="--degrees:${degrees}" aria-label="Study confidence: ${escapeHtml(levels[value].label)}. Select to change."></button>
      <span class="progress-label" id="progressLabel">${escapeHtml(levels[value].label)}</span>
    </div>`;
}

function bindProgress(data) {
  const ring = document.getElementById("progressRing");
  const label = document.getElementById("progressLabel");
  if (!ring || !label) return;
  ring.addEventListener("click", () => {
    const levels = data.progress_control.levels;
    const next = (getProgress(data.case_id) + 1) % levels.length;
    setProgress(data.case_id, next);
    ring.style.setProperty("--degrees", `${next * 120}deg`);
    ring.setAttribute("aria-label", `Study confidence: ${levels[next].label}. Select to change.`);
    label.textContent = levels[next].label;
    renderNavigation();
  });
}

function hintButtons(hintIds, data) {
  if (!hintIds || hintIds.length === 0) return "";
  const hints = new Map(data.hints.map((item) => [item.hint_id, item]));
  return hintIds.map((hintId) => {
    const hint = hints.get(hintId);
    if (!hint) return "";
    const panelId = `panel-${hintId}`;
    return `
      <button class="hint-button" aria-expanded="false" aria-controls="${panelId}" data-hint="${hintId}">Hint</button>
      <section class="hint-panel" id="${panelId}">
        <p class="hint-prompt">${escapeHtml(hint.visible_hint)}</p>
        <div class="hint-grid">
          <p class="hint-line"><strong>Notice</strong>${escapeHtml(hint.expanded.observe)}</p>
          <p class="hint-line"><strong>Connect</strong>${escapeHtml(hint.expanded.connect)}</p>
          <p class="hint-line"><strong>Mechanism</strong>${escapeHtml(hint.expanded.mechanism)}</p>
          <p class="hint-line"><strong>Weight</strong>${escapeHtml(hint.expanded.clinical_weight)}</p>
          <p class="hint-line"><strong>Next thought</strong>${escapeHtml(hint.expanded.next_thought)}</p>
        </div>
      </section>`;
  }).join("");
}

function bindHints() {
  document.querySelectorAll(".hint-button").forEach((button) => {
    button.addEventListener("click", () => {
      const panel = document.getElementById(button.getAttribute("aria-controls"));
      const isOpen = button.getAttribute("aria-expanded") === "true";
      button.setAttribute("aria-expanded", String(!isOpen));
      panel?.classList.toggle("open", !isOpen);
    });
  });
}

function clockCard(title, clock) {
  const segments = clock.segments.map((segment) => `
    <div class="clock-segment">
      <span class="clock-time">${segment.start_second}s to ${segment.end_second}s</span>
      <span>${escapeHtml(segment.label)}: ${escapeHtml(segment.focus || segment.move_on_signal || "")}</span>
    </div>`).join("");
  return `
    <section class="clock-card">
      <div class="clock-head">
        <div class="clock-ring" aria-hidden="true"></div>
        <div><div class="clock-title">${escapeHtml(title)}</div><div class="clock-total">${clock.total_seconds} seconds</div></div>
      </div>
      ${segments}
    </section>`;
}

function viewTabs(caseId, view) {
  return `
    <nav class="view-tabs" aria-label="Case views">
      <a href="${caseUrl(caseId, "stem")}" ${view === "stem" ? 'aria-current="page"' : ""}>Stem</a>
      <a href="${caseUrl(caseId, "script")}" ${view === "script" ? 'aria-current="page"' : ""}>Script</a>
    </nav>`;
}

function renderStem(data) {
  const nodes = data.stem_page.stem_nodes.map((node) => `
    <div class="stem-node" id="${node.stem_id}">
      <p>${escapeHtml(node.text)}</p>
      ${hintButtons(node.hint_ids, data)}
    </div>`).join("");
  const tasks = data.stem_page.tasks.map((task) => `
    <article class="task" id="${task.task_id}">
      <div class="task-head"><span class="anchor-symbol" aria-hidden="true">${escapeHtml(task.anchor.symbol)}</span><span>${escapeHtml(task.text)}</span></div>
      <p class="task-scope">${escapeHtml(task.scope)}</p>
      ${hintButtons(task.hint_ids, data)}
    </article>`).join("");
  screen.innerHTML = `
    <div class="top-row">${viewTabs(data.case_id, "stem")}${progressControl(data)}</div>
    <p class="eyebrow">${escapeHtml(data.navigation.phase_label)} · ${escapeHtml(data.navigation.pattern_label)}</p>
    <h1>${escapeHtml(data.title)}</h1>
    <div class="clocks">${clockCard("Reading map", data.clocks.reading)}${clockCard("Performance map", data.clocks.performance)}</div>
    <section class="station-card">
      <p class="eyebrow">${escapeHtml(data.stem_page.heading)}</p>
      ${nodes}
      <h2>Your tasks</h2>
      <div class="task-list">${tasks}</div>
    </section>`;
}

function renderScript(data) {
  const turns = data.script_page.turns.map((turn) => `
    <article class="turn" data-speaker="${turn.speaker}" id="${turn.turn_id}">
      <p class="speaker">${escapeHtml(turn.speaker)}</p>
      <p class="turn-text">${escapeHtml(turn.text)}</p>
      ${hintButtons(turn.hint_ids, data)}
    </article>`).join("");
  screen.innerHTML = `
    <div class="top-row">${viewTabs(data.case_id, "script")}${progressControl(data)}</div>
    <p class="eyebrow">${escapeHtml(data.navigation.phase_label)} · ${escapeHtml(data.navigation.pattern_label)}</p>
    <h1>${escapeHtml(data.title)}</h1>
    <section class="script" aria-label="Complete station script">${turns}</section>`;
}

function renderNavigation() {
  if (!state.index) return;
  const phases = state.index.phases || [];
  if (phases.length === 0) {
    nav.innerHTML = '<p class="empty">No study-ready cases.</p>';
    return;
  }
  nav.innerHTML = phases.map((phase) => `
    <details class="nav-phase" open>
      <summary>${escapeHtml(phase.label)}</summary>
      ${phase.patterns.map((pattern) => `
        <section class="nav-pattern">
          <p class="nav-pattern-title">${escapeHtml(pattern.label)}</p>
          ${pattern.cases.map((item) => {
            const progress = getProgress(item.case_id);
            const degrees = progress * 120;
            return `<a class="nav-case" href="${caseUrl(item.case_id, "stem")}"><span class="case-dot" style="background:conic-gradient(currentColor ${degrees}deg, transparent 0)" aria-hidden="true"></span><span>${escapeHtml(item.title)}</span><span class="visually-hidden">Progress: ${escapeHtml(state.index.progress_labels?.[progress] || String(progress))}</span></a>`;
          }).join("")}
        </section>`).join("")}
    </details>`).join("");
}

async function loadJson(path) {
  const response = await fetch(path, {cache: "no-store"});
  if (!response.ok) throw new Error(`Could not load ${path}`);
  return response.json();
}

async function init() {
  try {
    state.index = await loadJson("data/index.json");
    renderNavigation();
    const params = query();
    const caseId = params.get("case");
    const view = params.get("view") === "script" ? "script" : "stem";
    if (!caseId) {
      screen.innerHTML = '<section class="empty"><p class="eyebrow">Study library</p><h1>Choose a case.</h1><p>Only clinician-approved cases appear here.</p></section>';
      return;
    }
    const item = (state.index.cases || []).find((entry) => entry.case_id === caseId);
    if (!item) throw new Error("This case is not in the study-ready index.");
    state.currentCase = await loadJson(item.file);
    if (view === "script") renderScript(state.currentCase); else renderStem(state.currentCase);
    bindHints();
    bindProgress(state.currentCase);
    screen.focus();
  } catch (error) {
    screen.innerHTML = `<section class="empty"><h1>Display stopped.</h1><p>${escapeHtml(error.message)}</p></section>`;
  }
}

init();
