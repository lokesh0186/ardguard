# Evidence applicability fallback

Both evidence observations are cryptographically valid. The evidence associated with
rank one names a different subject digest, so it is authentic but not applicable to
that candidate. Rank two has matching evidence and is selected.

```bash
ardguard evaluate \
  --discovery-response examples/evidence/discovery.json \
  --task examples/evidence/task.json \
  --policy examples/evidence/policy.json \
  --facts examples/evidence/facts.json
```
