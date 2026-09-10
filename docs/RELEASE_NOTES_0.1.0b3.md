# ARDGuard 0.1.0b3

Beta 3 adds a compact extensible eligibility kernel while retaining the Beta 2 v1 API.

Highlights:

- generic requirements, facts, provider and evaluator interfaces;
- explicit provider trust by ID, version, and fact namespace;
- deterministic handling of multiple and conflicting facts;
- content-addressed decision receipts;
- JSON stdin/stdout and a loopback-only HTTP service;
- experimental MCP, A2A, OpenAPI, Skill, identity, evidence, and requirement packs;
- sparse ARD v0.91 Search result compatibility;
- bounded URL resolution with network disabled by default.

ARDGuard preserves discovery order, never treats relevance as eligibility, and never
invokes the selected resource. Experimental surfaces are labeled in the support matrix.
