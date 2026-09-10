# Third-party provider example

This minimal package registers `example.region-provider` through the
`ardguard.fact_providers` entry-point group. It requires no ARDGuard source change.
Loading remains opt in.

The example accepts a configured map that stands in for an independently queried
deployment control plane. It does not trust the candidate's catalog metadata.
