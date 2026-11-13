"""
Pydantic schemas for Recommendation Outcome History (R1), Fingerprinting (R2),
Current Condition Awareness (R3), Recommendation Decision Engine (R4), and
Explanation & Auditability (R6).

Defines serialization models for historical recommendation lifecycle queries,
structural fingerprint matches, current-condition evaluation results, R4 decisions,
and R6 structured audit explanations.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class RecommendationOutcomeResponse(BaseModel):
    """Response model representing the historical lifecycle of a recommendation."""
    id: int
    recommendation_id: str
    action_id: str
    session_id: int
    warehouse_id: int
    user_id: Optional[int] = None
    action_type: str
    target: Optional[Dict[str, Any]] = None
    approval_id: Optional[int] = None
    execution_id: Optional[int] = None
    verification_id: Optional[int] = None
    reanalysis_id: Optional[int] = None
    approval_status: Optional[str] = "PROPOSED"
    execution_status: Optional[str] = "PENDING"
    verification_status: Optional[str] = "PENDING"
    reanalysis_status: Optional[str] = "PENDING"
    objective_status: Optional[str] = "PENDING"
    final_outcome: str
    fingerprint: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RecommendationHistoryListResponse(BaseModel):
    """Paginated list of recommendation outcome records."""
    items: List[RecommendationOutcomeResponse]
    total: int
    limit: int
    offset: int


class HistoricalMatchSummaryResponse(BaseModel):
    """Structural fingerprint match summary payload (R2)."""
    fingerprint: str
    match_found: bool
    match_count: int
    matches: List[RecommendationOutcomeResponse]


class EvidenceItem(BaseModel):
    """Structured machine-readable evidence item for R3 evaluation."""
    source: str
    field: str
    value: Optional[Any] = None
    interpretation: str


class CurrentConditionResponse(BaseModel):
    """Structured R3 current-condition evaluation result payload."""
    recommendation_id: Optional[str] = None
    fingerprint: Optional[str] = None
    warehouse_id: int
    action_type: str
    target: Optional[Dict[str, Any]] = None
    condition_status: str  # PRESENT | RESOLVED | UNCERTAIN | NOT_MEASURABLE
    condition_type: str
    evidence: List[EvidenceItem] = []
    evaluated_at: str
    measurement_available: bool
    reason: str
    historical_match: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)


class RecommendationDecisionResponse(BaseModel):
    """Structured R4 recommendation lifecycle decision payload."""
    recommendation_id: Optional[str] = None
    fingerprint: Optional[str] = None
    action_type: str
    target: Optional[Dict[str, Any]] = None
    decision: str  # PROPOSE | SUPPRESS | REVIEW
    reason_code: str
    reason: str
    historical_outcome: Optional[str] = None
    current_condition_status: Optional[str] = None
    evidence: List[EvidenceItem] = []
    evaluated_at: str

    model_config = ConfigDict(from_attributes=True)


class RecommendationDecisionBatchResponse(BaseModel):
    """Batch R4 decision response for multiple recommendation candidates."""
    total_candidates: int
    propose_count: int
    suppress_count: int
    review_count: int
    decisions: List[RecommendationDecisionResponse]
    propose_candidates: List[Dict[str, Any]] = []
    suppress_candidates: List[Dict[str, Any]] = []
    review_candidates: List[Dict[str, Any]] = []

    model_config = ConfigDict(from_attributes=True)


class HistoricalContextSummary(BaseModel):
    """R6 Historical outcome context summary."""
    match_found: bool
    fingerprint: Optional[str] = None
    historical_outcome: Optional[str] = None
    previous_final_outcome: Optional[str] = None
    previous_action_id: Optional[Any] = None
    previous_session_id: Optional[Any] = None
    summary: Optional[str] = ""

    model_config = ConfigDict(from_attributes=True)


class ConditionContextSummary(BaseModel):
    """R6 Current warehouse condition context summary."""
    condition_status: Optional[str] = "UNCERTAIN"
    condition_state: Optional[str] = "UNCERTAIN"
    condition_type: Optional[str] = "UNKNOWN"
    observed_reason: Optional[str] = ""
    observed_facts: Optional[str] = ""
    measurement_available: bool = True
    evidence: List[EvidenceItem] = []

    model_config = ConfigDict(from_attributes=True)


class UncertaintyDetail(BaseModel):
    """R6 Uncertainty disclosure details."""
    uncertainty_type: Optional[str] = "GENERIC"
    description: Optional[str] = ""
    status: Optional[str] = "UNCERTAIN"
    reason: Optional[str] = ""

    model_config = ConfigDict(from_attributes=True)


class RecommendationExplanationResponse(BaseModel):
    """Structured R6 recommendation explanation and auditability response payload."""
    recommendation_id: str
    fingerprint: Optional[str] = None
    action_type: str
    target: Optional[Dict[str, Any]] = None
    decision: str  # PROPOSE | SUPPRESS | REVIEW
    decision_reason_code: Optional[str] = "CURRENT_CONDITION_UNAVAILABLE"
    reason_code: Optional[str] = "CURRENT_CONDITION_UNAVAILABLE"
    decision_reason: Optional[str] = ""
    lifecycle_state: str  # ACTIVE | SUPPRESSED | REVIEW | REOPENED
    summary: str
    historical_context: HistoricalContextSummary
    current_condition: ConditionContextSummary
    decision_evidence: List[EvidenceItem] = []
    lifecycle_evidence: List[EvidenceItem] = []
    uncertainty: Optional[UncertaintyDetail] = None
    generated_at: str

    model_config = ConfigDict(from_attributes=True)
