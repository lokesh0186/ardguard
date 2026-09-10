# Eligibility packs

Packs are documented combinations of fact types and generic constraints. They are not
universal secure defaults. Metadata alone is never treated as verified unless a
provider establishes the corresponding fact.

| Pack | Maturity | Facts | Boundary |
| --- | --- | --- | --- |
| Capability | Supported through v1, v2 compatibility tested | Verified operations | Advertised and verified capability remain separate. |
| Artifact evidence | Supported through v1, generalized SPI experimental | Authenticity, signer, predicate, subject digest, association | Validity and applicability remain separate. |
| Least authority | Supported through v1, v2 compatibility tested | Granted scope | Maximum authority is operator policy, not an ARD mandate. |
| Publisher identity | Experimental | Verified publisher identity and identity type | Static fixtures only; core is not a DID resolver. |
| Access feasibility | Experimental | Auth mechanism and credential category availability | Secret values are prohibited. No authentication is performed. |
| Dependencies | Experimental | Supplied dependency availability and verified usability | Depth is bounded, cycles fail, and nothing is installed. |
| Deployment and compliance | Experimental | Environment, region, residency, assertion, deployment identity | Assertions need a provider and applicable evidence. |
| Version and freshness | Experimental | Version, updated time, deprecation extension, replacement, expiration | Lifecycle extensions are not claimed as normative ARD v0.91 terms. |
| Usage and SLA | Experimental | Quota, request cost, availability, SLA class, degradation | No billing and no paid API calls. |
| Observed fitness | Experimental | Artifact binding, window, issuer, environment, vantage, freshness | No normative ARD shape is claimed. |
| Federation provenance | Experimental | Canonical and observed source, mirror state, digest, synchronization, trust | ARDGuard evaluates supplied facts; it does not federate or synchronize. |

Policy packs named `basic-capability`, `artifact-evidence`, `least-authority`,
`verified-resource`, and `enterprise-basic` are examples. Operators must review their
provider assumptions and unknown handling before deployment.
