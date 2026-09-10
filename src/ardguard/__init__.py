"""ARDGuard public API."""

from ardguard.decision import evaluate
from ardguard.models import (
    Candidate,
    CandidateEvaluation,
    CandidateVerdict,
    ContractError,
    Decision,
    FactSet,
    FactType,
    FinalDecision,
    Observation,
    ObservationState,
    Policy,
    TaskContract,
    VerifierOutcome,
)

__version__ = "0.1.0b2"

__all__ = [
    "Candidate",
    "CandidateEvaluation",
    "CandidateVerdict",
    "ContractError",
    "Decision",
    "FactSet",
    "FactType",
    "FinalDecision",
    "Observation",
    "ObservationState",
    "Policy",
    "TaskContract",
    "VerifierOutcome",
    "evaluate",
]
