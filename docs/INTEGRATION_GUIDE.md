# Integration guide

## Five-minute JSON path

1. Obtain a completed ARD SearchResponse.
2. Write a task contract that names the operation and required eligibility dimensions.
3. Obtain typed observations from providers you trust.
4. Run `ardguard evaluate`.
5. Inspect `outcome`, `selected_candidate_id`, and the candidate reasons.
6. Keep invocation in your own explicit caller path.

The complete offline files are under `examples/fallback`.

```bash
ardguard evaluate \
  --discovery-response examples/fallback/discovery.json \
  --task examples/fallback/task.json \
  --policy examples/fallback/policy.json \
  --facts examples/fallback/facts.json \
  --output decision.json
ardguard explain decision.json
```

## Python path

```python
from ardguard import FactSet, Policy, TaskContract, evaluate
from ardguard.adapters import parse_search_response

decision = evaluate(
    candidates=parse_search_response(search_response),
    task=TaskContract.from_mapping(task),
    policy=Policy.from_mapping(policy),
    facts=FactSet.from_mapping(facts),
)
```

`providers=(...)` may replace or supplement a FactSet. Duplicate observations for the
same candidate and fact type fail rather than vote.

## ARD and hf-discover path

```text
hf-discover or another ARD backend
                |
                v
         SearchResponse JSON
                |
                v
             ARDGuard
                |
                v
           Decision JSON
                |
                v
 explicit caller-controlled invocation
```

Use `--adapter hf-discover` to require the pinned hf-discover output fields. Use
`--adapter ard` for the minimum ARD v0.91 SearchResult projection.

## Error handling

- Exit 0: `SELECT`
- Exit 1: `ABSTAIN`
- Exit 2: invalid command or contract
- Exit 3: `DEFER`
- Exit 4: `ERROR`

Never treat a nonzero exit as evidence that a candidate's signature is invalid. Read
the decision and reason code.
