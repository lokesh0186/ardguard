# hf-discover integration

Beta 2 is qualified against hf-discover 1.3.7 at commit
`49c927439fcaa8f210cfd42186c0641acef579fa`.

```bash
hf-discover search "find a weather tool" --json > discovery.json
ardguard validate --kind hf-discover discovery.json
ardguard evaluate \
  --adapter hf-discover \
  --discovery-response discovery.json \
  --task task.json \
  --policy policy.json \
  --facts facts.json
```

The pinned adapter requires the fields emitted by the current hf-discover model,
including `identifier`, `displayName`, `type`, `score`, `source`, and exactly one of
`url` or `data`. It preserves order, score, metadata, and other opaque entry fields.

ARDGuard does not call Hugging Face, modify ranking, fetch a Space, install an MCP
server, or infer missing eligibility facts. Unsupported output shapes fail with an
actionable contract error.

The repository includes a synthetic wire-compatible fixture at
`examples/hf_discover/search-response-1.3.7.json`. It contains no live account or
service dependency.
