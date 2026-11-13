"""
Automation action approval Pydantic schemas.

Input validation and output response serialization for the Phase 4 User Approval Gate.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ApprovalRequest(BaseModel):
    """Payload for approving or rejecting an action plan."""

    reason: Optional[str] = Field(
        None,
        max_length=1000,
        description="Optional reason or note for the approval/rejection decision.",
    )


class ApprovalResponse(BaseModel):
    """Response returned after an action plan is approved or rejected."""

    action_id: str
    session_id: str
    warehouse_id: int
    status: str  # APPROVED or REJECTED
    decision: str  # APPROVE or REJECT
    approved_by: str  # username / email of authenticated user
    approved_at: datetime
    executed: bool = False  # Always False in Phase 4!
    reason: Optional[str] = None
    message: str


class ActionPlanDetail(BaseModel):
    """Detailed action plan representation including current approval status."""

    action_id: str
    recommendation_type: str
    action_type: str
    status: str  # PROPOSED, APPROVED, REJECTED
    automation_status: str
    target: Dict[str, Any]
    description: str
    statement: Optional[str] = None
    parameters: Dict[str, Any]
    risk_level: str
    impact_level: str
    safety_class: str
    preconditions: List[str]
    safety_checks: List[str]
    rollback_plan: Dict[str, Any]
    verification_plan: Dict[str, Any]
    requires_approval: bool
    requires_verification: bool
    is_destructive: bool
    is_reversible: bool
    is_executable: bool
    executed: bool = False
    verification_status: Optional[str] = "PENDING"
    created_at: str
    source_agent: str
    evidence: List[Any]
    approval: Optional[Dict[str, Any]] = None


class ExecutionResultResponse(BaseModel):
    """Response returned after executing an approved action plan."""

    execution_id: int
    action_id: str
    session_id: str
    warehouse_id: int
    status: str  # COMPLETED or FAILED
    action_type: str
    started_at: datetime
    completed_at: datetime
    duration_ms: float
    executed: bool
    message: str
    verification_status: str = "PENDING"
    error_message: Optional[str] = None


class VerificationCheckDetail(BaseModel):
    """Structured check result for a single verification check."""

    check_id: str
    description: str
    expected: Optional[Any] = None
    observed: Optional[Any] = None
    status: str  # PASS, FAIL, INCONCLUSIVE
    evidence: str


class VerificationResultResponse(BaseModel):
    """Response returned after performing evidence-based catalog verification."""

    verification_id: str
    execution_id: int
    action_id: str
    session_id: str
    warehouse_id: int
    status: str  # VERIFIED, VERIFICATION_FAILED, INCONCLUSIVE
    verified: Optional[bool] = None
    action_type: str
    expected_state: Dict[str, Any]
    observed_state: Dict[str, Any]
    evidence: List[str]
    checks: List[VerificationCheckDetail]
    started_at: datetime
    completed_at: datetime
    duration_ms: float
    message: str
    error_message: Optional[str] = None


class StateComparisonDetail(BaseModel):
    """Structured comparison item between pre-execution and post-execution state."""

    metric: str
    before: Optional[Any] = None
    after: Optional[Any] = None
    status: str  # MATCH, MISMATCH, NOT_MEASURED
    evidence: Optional[str] = None
    reason: Optional[str] = None


class SupervisorReanalysisResponse(BaseModel):
    """Response returned after post-execution supervisor re-analysis."""

    reanalysis_id: str
    execution_id: int
    verification_id: Optional[int] = None
    action_id: str
    session_id: str
    warehouse_id: int
    status: str  # SUCCESSFUL_OUTCOME, UNSUCCESSFUL_OUTCOME, UNCERTAIN_OUTCOME
    objective_status: str  # ACHIEVED, NOT_ACHIEVED, UNCERTAIN
    action_type: str
    before_state: Dict[str, Any]
    after_state: Dict[str, Any]
    comparisons: List[StateComparisonDetail]
    findings: List[str]
    conclusion: str
    follow_up_required: bool
    follow_up_type: str  # NONE, OBSERVATION, ANALYSIS, RECOMMENDATION
    follow_up_details: Optional[Dict[str, Any]] = None
    started_at: datetime
    completed_at: datetime
    duration_ms: float
    message: str
    error_message: Optional[str] = None


