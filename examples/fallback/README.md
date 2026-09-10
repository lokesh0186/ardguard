# Rank-preserving fallback

Rank one is more relevant but lacks the independently verified read capability. Rank
two satisfies capability, evidence, and authority requirements. Run:

```bash
ardguard evaluate \
  --discovery-response examples/fallback/discovery.json \
  --task examples/fallback/task.json \
  --policy examples/fallback/policy.json \
  --facts examples/fallback/facts.json
```

The result selects rank two and never invokes it.
