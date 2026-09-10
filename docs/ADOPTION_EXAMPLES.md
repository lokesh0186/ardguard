# Adoption examples

These are integration patterns, not claims about external project behavior.

## Client or connector

Insert ARDGuard after an ARD client receives ranked results and before it presents a
final install or invocation choice. Keep user confirmation unchanged.

## Gateway

Use a gateway's existing capability, identity, and authorization systems as providers.
ARDGuard composes those facts for one task and performs rank-preserving fallback. It
does not replace gateway authentication, governance, or scanning.

## Evidence-aware package selection

Verify evidence against its authentic bound artifact, retain the selected candidate's
artifact digest separately, and let ARDGuard enforce exact subject association. This
keeps authenticity and applicability distinct.

## Read-only task

Supply independently verified permission sets and configure a maximum containing only
the read operation. A write-capable alternative remains ineligible even when it can
produce the correct response.
