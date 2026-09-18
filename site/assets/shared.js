"use strict";

const snippets = {
  python: `from ardguard import FactSet, Policy, TaskContract, evaluate\nfrom ardguard.adapters import parse_search_response\n\ncandidates = parse_search_response(discovery_response)\ndecision = evaluate(\n    candidates=candidates,\n    task=TaskContract.from_mapping(task_document),\n    policy=Policy.from_mapping(policy_document),\n    facts=FactSet.from_mapping(fact_document),\n)\nprint(decision.to_dict())`,
  stdin: `some-discovery-command \\\n  | ardguard evaluate --stdin --json`,
  http: `curl --request POST http://127.0.0.1:8765/v1/evaluate \\\n  --header 'Content-Type: application/json' \\\n  --data @evaluate-bundle.json`,
  hf: `hf-discover search "read customer records" --json > discovery.json\n\nardguard evaluate \\\n  --adapter hf-discover \\\n  --discovery-response discovery.json \\\n  --task task.json --policy policy.json --facts facts.json`,
};

async function copyText(text, button) {
  try {
    await navigator.clipboard.writeText(text);
    const previous = button.textContent;
    button.textContent = "Copied";
    window.setTimeout(() => {
      button.textContent = previous;
    }, 1600);
  } catch {
    button.textContent = "Copy unavailable";
  }
}

document.querySelectorAll("[data-copy-target]").forEach((button) => {
  button.addEventListener("click", () => {
    const target = document.getElementById(button.dataset.copyTarget);
    if (target) copyText(target.textContent, button);
  });
});

document.querySelectorAll("[data-snippet-select]").forEach((select) => {
  const output = document.getElementById(select.dataset.output);
  if (!output) return;
  const update = () => {
    output.textContent = snippets[select.value] || snippets.python;
  };
  select.addEventListener("change", update);
  update();
});

document.querySelectorAll("[data-copy-snippet]").forEach((button) => {
  button.addEventListener("click", () => {
    const output = document.getElementById(button.dataset.copySnippet);
    if (output) copyText(output.textContent, button);
  });
});
