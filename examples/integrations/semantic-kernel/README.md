# Semantic Kernel community interoperability example

This downstream example places ARDGuard before Semantic Kernel's MCP plugin
connection and invocation path:

```text
ranked MCP candidates
        |
        v
ARDGuard task eligibility
        |
        v
selected candidate only
        |
        v
Semantic Kernel runtime authorization / invocation
```

The discovery order prefers `preferred`. A configured provider fact says that
the caller cannot satisfy its access requirement, while `fallback` is eligible.
ARDGuard preserves the ranks and selects `fallback`. Only the selected plugin is
then connected and invoked through Semantic Kernel.

This is a community interoperability example. It is not an official Microsoft
integration or endorsement. ARDGuard does not replace Semantic Kernel's runtime
authorization and does not invoke either resource itself.

The test is fully local: it uses fake MCP sessions, no model, no credentials,
and no network service.

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pytest -q test_reference.py
```

Expected result:

```text
1 passed
```
