"use strict";

const tableBody = document.querySelector("[data-home-candidates]");
const selected = document.querySelector("[data-home-selected]");
const reason = document.querySelector("[data-home-reason]");

function statusLabel(row) {
  if (row.selected) return ["Selected", "status-selected"];
  if (row.eligibility === "UNSATISFIED") return ["Ineligible", "status-unsatisfied"];
  if (row.eligibility === "INDETERMINATE") return ["Indeterminate", "status-indeterminate"];
  if (row.eligibility === "ERROR") return ["Error", "status-error"];
  return ["Eligible", "status-satisfied"];
}

async function loadHomeDecision() {
  if (!tableBody) return;
  try {
    const response = await fetch("./fixtures/evidence-wrong-resource.json", {
      credentials: "omit",
    });
    if (!response.ok) throw new Error("fixture unavailable");
    const fixture = await response.json();
    tableBody.replaceChildren();
    fixture.display.candidates.forEach((row) => {
      const tr = document.createElement("tr");
      const values = [
        `#${row.rank}`,
        row.label,
        row.evidence,
        row.access,
        row.authority,
      ];
      values.forEach((value, index) => {
        const td = document.createElement("td");
        td.textContent = value;
        if (index === 0) td.className = "rank";
        tr.append(td);
      });
      const [label, className] = statusLabel(row);
      const td = document.createElement("td");
      const span = document.createElement("span");
      span.className = `status ${className}`;
      span.textContent = label;
      td.append(span);
      tr.append(td);
      tableBody.append(tr);
    });
    const chosen = fixture.display.candidates.find((row) => row.selected);
    selected.textContent = chosen ? chosen.label : fixture.decision.outcome;
    reason.textContent = fixture.decision.reason_code;
  } catch {
    tableBody.replaceChildren();
    const tr = document.createElement("tr");
    const td = document.createElement("td");
    td.colSpan = 6;
    td.textContent = "The static decision fixture could not be loaded.";
    tr.append(td);
    tableBody.append(tr);
  }
}

loadHomeDecision();
