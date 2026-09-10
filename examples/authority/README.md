# Authority-aware fallback

Both resources may be relevant, but rank one has authority outside the task's maximum.
ARDGuard selects rank two, whose independently established permissions remain within
the operator's policy.

```bash
ardguard evaluate \
  --discovery-response examples/authority/discovery.json \
  --task examples/authority/task.json \
  --policy examples/authority/policy.json \
  --facts examples/authority/facts.json
```
