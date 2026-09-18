"use strict";

const state = { index: null, fixture: null };

function element(tag, options = {}) {
  const node = document.createElement(tag);
  if (options.className) node.className = options.className;
  if (options.text !== undefined) node.textContent = options.text;
  if (options.attrs) {
    Object.entries(options.attrs).forEach(([name, value]) => node.setAttribute(name, value));
  }
  return node;
}

function shortId(value) {
  return value.split(":").at(-1) || value;
}

function statusClass(status) {
  return {
    SATISFIED: "status-satisfied",
    UNSATISFIED: "status-unsatisfied",
    INDETERMINATE: "status-indeterminate",
    ERROR: "status-error",
  }[status] || "status-indeterminate";
}

function outcomeClass(outcome) {
  return `pill pill-${outcome.toLowerCase()}`;
}

function setAll(selector, value) {
  document.querySelectorAll(selector).forEach((node) => {
    node.textContent = value;
  });
}

function renderScenarioNavigation() {
  const nav = document.querySelector("[data-scenario-nav]");
  const heading = element("h2", { text: "Scenarios" });
  const picker = element("label", { className: "mobile-scenario-picker" });
  picker.append(element("span", { text: "Scenario" }));
  const select = element("select", {
    className: "snippet-select",
    attrs: { "data-scenario-select": "" },
  });
  picker.append(select);
  nav.replaceChildren(heading, picker);
  state.index.scenarios.forEach((item) => {
    select.append(element("option", { text: item.title, attrs: { value: item.id } }));
    const button = element("button", {
      className: "scenario-button",
      attrs: { type: "button", "data-scenario": item.id },
    });
    button.append(element("strong", { text: item.title }));
    button.append(element("span", { text: item.outcome }));
    button.addEventListener("click", () => selectScenario(item.id, true));
    nav.append(button);
  });
  select.addEventListener("change", () => selectScenario(select.value, true));
}

function renderCandidateTable() {
  const body = document.querySelector("[data-candidate-rows]");
  body.replaceChildren();
  state.fixture.display.candidates.forEach((candidate) => {
    const row = element("tr");
    [
      `#${candidate.rank}`,
      candidate.label,
      String(candidate.score),
      candidate.evidence,
      candidate.access,
      candidate.authority,
    ].forEach((value, index) => {
      const cell = element("td", { text: value });
      if (index === 0) cell.className = "rank";
      row.append(cell);
    });
    const statusCell = element("td");
    const label = candidate.selected ? "Selected" : candidate.eligibility;
    const className = candidate.selected ? "status-selected" : statusClass(candidate.eligibility);
    statusCell.append(element("span", { className: `status ${className}`, text: label }));
    row.append(statusCell);
    body.append(row);
  });
}

function renderSummary() {
  const fixture = state.fixture;
  document.querySelector("[data-scenario-title]").textContent = fixture.title;
  document.querySelector("[data-scenario-summary]").textContent = fixture.summary;
  document.querySelector("[data-scenario-lesson]").textContent = fixture.lesson;
  document.querySelectorAll("[data-outcome]").forEach((outcome) => {
    outcome.className = outcomeClass(fixture.decision.outcome);
    outcome.textContent = fixture.decision.outcome;
  });
  setAll("[data-outcome-text]", fixture.decision.outcome);
  setAll("[data-reason]", fixture.decision.reason_code);
  setAll(
    "[data-selected]",
    fixture.decision.selected_candidate_id
      ? shortId(fixture.decision.selected_candidate_id)
      : "none",
  );
  setAll("[data-version]", fixture.package.version);
  setAll("[data-invocation]", fixture.invocation);
}

function renderRequirements() {
  const container = document.querySelector("[data-requirements]");
  container.replaceChildren();
  state.fixture.decision.evaluations.forEach((evaluation) => {
    evaluation.requirements.forEach((verdict) => {
      const row = element("article", { className: "requirement-row" });
      const identity = element("div");
      identity.append(element("strong", { text: `${shortId(evaluation.candidate_id)} · ${verdict.requirement_id}` }));
      identity.append(element("div", { className: "microcopy", text: `rank #${evaluation.rank}` }));
      row.append(identity);
      row.append(element("span", { className: `status ${statusClass(verdict.status)}`, text: verdict.status }));
      const reason = element("code", { text: verdict.reason_code });
      row.append(reason);
      container.append(row);
    });
  });
}

function renderCandidates() {
  const container = document.querySelector("[data-candidate-cards]");
  container.replaceChildren();
  state.fixture.decision.evaluations.forEach((evaluation) => {
    const display = state.fixture.display.candidates.find(
      (candidate) => candidate.candidate_id === evaluation.candidate_id,
    );
    const card = element("dl", { className: "receipt-card" });
    [
      ["Candidate", display ? display.label : shortId(evaluation.candidate_id)],
      ["Original rank", `#${evaluation.rank}`],
      ["Original score", String(evaluation.score)],
      ["Eligibility", evaluation.status],
      ["Failed / uncertain requirements", evaluation.requirements.filter((item) => item.status !== "SATISFIED").map((item) => item.requirement_id).join(", ") || "none"],
    ].forEach(([term, value]) => {
      card.append(element("dt", { text: term }));
      card.append(element("dd", { text: value }));
    });
    container.append(card);
  });
}

function renderProvenance() {
  const receipt = state.fixture.decision.receipt;
  const container = document.querySelector("[data-provenance]");
  container.replaceChildren();
  const rows = [
    ["Task hash", receipt.task_sha256],
    ["Candidate-set hash", receipt.candidate_set_sha256],
    ["Policy hash", receipt.policy_sha256],
    ["Receipt hash", receipt.receipt_sha256],
    ["Decision hash", state.fixture.decision.decision_sha256],
    ["Providers", receipt.provider_identities.map((item) => `${item.provider_id}@${item.provider_version}`).join(", ") || "none"],
    ["Fact hashes", `${receipt.fact_sha256.length} retained`],
    ["Software version", receipt.software_version],
  ];
  rows.forEach(([term, value]) => {
    const card = element("dl", { className: "receipt-card" });
    card.append(element("dt", { text: term }));
    card.append(element("dd", { text: value }));
    container.append(card);
  });
}

function renderRaw() {
  document.querySelector("[data-raw-json]").textContent = JSON.stringify(state.fixture, null, 2);
  document.querySelector("[data-input-json]").textContent = JSON.stringify(state.fixture.input, null, 2);
  document.querySelector("[data-decision-json]").textContent = JSON.stringify(state.fixture.decision, null, 2);
}

function renderScenario() {
  renderSummary();
  renderCandidateTable();
  renderRequirements();
  renderCandidates();
  renderProvenance();
  renderRaw();
  document.querySelectorAll("[data-scenario]").forEach((button) => {
    button.setAttribute("aria-current", String(button.dataset.scenario === state.fixture.id));
  });
  document.querySelector("[data-scenario-select]").value = state.fixture.id;
  document.title = `${state.fixture.title} | ARDGuard Decision Explorer`;
}

async function selectScenario(id, announce = false) {
  const item = state.index.scenarios.find((scenario) => scenario.id === id);
  if (!item) return;
  const response = await fetch(`../fixtures/${item.file}`, { credentials: "omit" });
  if (!response.ok) throw new Error(`unable to load ${item.file}`);
  state.fixture = await response.json();
  window.history.replaceState(null, "", `#${id}`);
  renderScenario();
  if (announce) {
    document.querySelector("[data-scenario-title]").focus({ preventScroll: true });
  }
}

function setupTabs() {
  const buttons = [...document.querySelectorAll("[role=tab]")];
  buttons.forEach((button, index) => {
    button.addEventListener("click", () => activateTab(button));
    button.addEventListener("keydown", (event) => {
      if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
      event.preventDefault();
      let target = index;
      if (event.key === "ArrowLeft") target = (index - 1 + buttons.length) % buttons.length;
      if (event.key === "ArrowRight") target = (index + 1) % buttons.length;
      if (event.key === "Home") target = 0;
      if (event.key === "End") target = buttons.length - 1;
      activateTab(buttons[target]);
      buttons[target].focus();
    });
  });
}

function activateTab(active) {
  document.querySelectorAll("[role=tab]").forEach((button) => {
    const selected = button === active;
    button.setAttribute("aria-selected", String(selected));
    button.tabIndex = selected ? 0 : -1;
    const panel = document.getElementById(button.getAttribute("aria-controls"));
    panel.hidden = !selected;
  });
}

function setupDeveloperView() {
  const button = document.querySelector("[data-developer-toggle]");
  const panel = document.querySelector("[data-developer-panel]");
  button.addEventListener("click", () => {
    const expanded = button.getAttribute("aria-expanded") === "true";
    button.setAttribute("aria-expanded", String(!expanded));
    button.textContent = expanded ? "Show developer view" : "Hide developer view";
    panel.hidden = expanded;
  });
}

async function initialize() {
  setupTabs();
  setupDeveloperView();
  const response = await fetch("../fixtures/index.json", { credentials: "omit" });
  if (!response.ok) throw new Error("fixture index unavailable");
  state.index = await response.json();
  renderScenarioNavigation();
  const requested = window.location.hash.slice(1);
  const selected = state.index.scenarios.some((item) => item.id === requested)
    ? requested
    : state.index.default_scenario;
  await selectScenario(selected);
}

initialize().catch(() => {
  const main = document.querySelector("[data-explorer-main]");
  main.replaceChildren(element("p", { className: "callout callout-warning", text: "The static decision fixtures could not be loaded. No evaluation was attempted." }));
});
