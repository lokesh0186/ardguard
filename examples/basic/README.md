# Basic capability decision

This one-candidate example uses only an independently established capability fact.

```bash
ardguard evaluate \
  --discovery-response examples/basic/discovery.json \
  --task examples/basic/task.json \
  --policy examples/basic/policy.json \
  --facts examples/basic/facts.json
```

The decision is `SELECT`. ARDGuard returns the candidate identity and explanation, but
does not invoke it.
