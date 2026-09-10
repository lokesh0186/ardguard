# Authority policy

Least authority is an operator-defined eligibility profile. It is not a normative ARD
requirement and ARDGuard does not infer a universal privilege order.

The Beta 1 contract uses exact permission sets:

- `required_permissions` lists what the task must be able to do;
- `maximum_permissions` lists every permission the operator permits;
- the provider reports independently verified `granted_permissions`.

A candidate is authority-eligible only when the required set is contained in its
granted set and its granted set is contained in the maximum set.

```json
{
  "required": true,
  "required_permissions": ["records.read"],
  "maximum_permissions": ["records.read"]
}
```

A candidate granting both `records.read` and `records.write` is ineligible under this
profile even if it can complete the read task. Deployments with roles, scopes, or graph
semantics should implement a provider that maps their independently verified authority
into a stable permission vocabulary.
