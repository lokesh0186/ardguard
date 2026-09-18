"use strict";

const search = document.querySelector("[data-doc-search]");
const results = document.querySelector("[data-search-results]");
const sections = [...document.querySelectorAll("[data-search-entry]")];

function showResults(query) {
  results.replaceChildren();
  const normalized = query.trim().toLocaleLowerCase();
  if (normalized.length < 2) {
    results.hidden = true;
    return;
  }
  const matches = sections
    .filter((section) => section.textContent.toLocaleLowerCase().includes(normalized))
    .slice(0, 8);
  results.hidden = false;
  if (!matches.length) {
    const empty = document.createElement("p");
    empty.className = "search-result";
    empty.textContent = "No documentation section matches that phrase.";
    results.append(empty);
    return;
  }
  matches.forEach((section) => {
    const card = document.createElement("article");
    card.className = "search-result";
    const link = document.createElement("a");
    link.href = `#${section.id}`;
    const heading = section.querySelector("h2");
    link.textContent = heading ? heading.textContent : section.id;
    const summary = document.createElement("p");
    summary.textContent = section.dataset.searchSummary || "Open this section.";
    card.append(link, summary);
    results.append(card);
  });
}

if (search && results) {
  search.addEventListener("input", () => showResults(search.value));
}
