from __future__ import annotations

import copy

from ardguard.decision import evaluate
from ardguard.models import CandidateVerdict, FactSet


def _changed_facts(document, candidate_suffix: str, fact_type: str, update) -> FactSet:
    changed = copy.deepcopy(document)
    row = next(
        item
        for item in changed["observations"]
        if item["candidate_id"].endswith(candidate_suffix) and item["fact_type"] == fact_type
    )
    update(row)
    return FactSet.from_mapping(changed)


def test_wrong_evidence_subject_is_ineligible(fallback_inputs, fallback_documents) -> None:
    candidates, task, policy, _ = fallback_inputs
    _, _, _, facts_document = fallback_documents
    facts = _changed_facts(
        facts_document,
        "rank-two",
        "evidence",
        lambda row: row["payload"].update({"subject_sha256": ["f" * 64]}),
    )
    decision = evaluate(candidates=candidates, task=task, policy=policy, facts=facts)
    second = next(item for item in decision.evaluations if item.candidate_id.endswith("rank-two"))
    assert second.verdict is CandidateVerdict.INELIGIBLE
    assert "evidence.subject_mismatch" in [reason.value for reason in second.reasons]


def test_rank_cannot_make_wrong_subject_applicable(fallback_inputs, fallback_documents) -> None:
    candidates, task, policy, _ = fallback_inputs
    _, _, _, facts_document = fallback_documents
    facts = _changed_facts(
        facts_document,
        "rank-one",
        "evidence",
        lambda row: row["payload"].update({"subject_sha256": ["f" * 64]}),
    )
    decision = evaluate(candidates=candidates, task=task, policy=policy, facts=facts)
    assert "evidence.subject_mismatch" in [
        reason.value for reason in decision.evaluations[0].reasons
    ]


def test_excess_authority_cannot_improve_eligibility(fallback_inputs, fallback_documents) -> None:
    candidates, task, policy, _ = fallback_inputs
    _, _, _, facts_document = fallback_documents
    facts = _changed_facts(
        facts_document,
        "rank-two",
        "authority",
        lambda row: row["payload"].update(
            {"granted_permissions": ["records.read", "records.write"]}
        ),
    )
    decision = evaluate(candidates=candidates, task=task, policy=policy, facts=facts)
    second = next(item for item in decision.evaluations if item.candidate_id.endswith("rank-two"))
    assert second.verdict is CandidateVerdict.INELIGIBLE
    assert "authority.excessive" in [reason.value for reason in second.reasons]


def test_lower_score_never_changes_ineligible_to_eligible(fallback_inputs) -> None:
    candidates, task, policy, facts = fallback_inputs
    lowered = candidates[0].__class__(
        resource_id=candidates[0].resource_id,
        source=candidates[0].source,
        rank=candidates[0].rank,
        score=0,
        media_type=candidates[0].media_type,
        metadata=candidates[0].metadata,
        original=candidates[0].original,
    )
    decision = evaluate(candidates=(lowered, candidates[1]), task=task, policy=policy, facts=facts)
    assert decision.evaluations[0].verdict is CandidateVerdict.INELIGIBLE
