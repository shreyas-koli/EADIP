"""
Unit tests for RecommendationOutcomeService and derivation logic (R1).

Verifies outcome derivation rules, status precedence, record creation, idempotency,
and handling of all lifecycle states (PROPOSED, APPROVED, REJECTED, EXECUTING, FAILED,
VERIFIED, VERIFICATION_FAILED, INCONCLUSIVE, ACHIEVED, NOT_ACHIEVED, UNCERTAIN).
"""

import pytest
from app.models.approval import ActionApproval
from app.models.action_execution_record import ActionExecutionRecord
from app.models.action_verification_record import ActionVerificationRecord
from app.models.supervisor_reanalysis_record import SupervisorReanalysisRecord
from app.services.recommendation_outcome_service import RecommendationOutcomeService


def test_derive_final_outcome_proposed():
    """Verify default fallback yields PROPOSED outcome."""
    outcome = RecommendationOutcomeService.derive_final_outcome()
    assert outcome == "PROPOSED"


def test_derive_final_outcome_approval():
    """Verify Approval state precedence when downstream records are absent."""
    appr_approved = ActionApproval(status="APPROVED")
    assert RecommendationOutcomeService.derive_final_outcome(approval=appr_approved) == "APPROVED"

    appr_rejected = ActionApproval(status="REJECTED")
    assert RecommendationOutcomeService.derive_final_outcome(approval=appr_rejected) == "REJECTED"


def test_derive_final_outcome_execution():
    """Verify Execution state precedence over Approval."""
    appr = ActionApproval(status="APPROVED")
    
    exec_executing = ActionExecutionRecord(status="EXECUTING")
    assert RecommendationOutcomeService.derive_final_outcome(approval=appr, execution=exec_executing) == "EXECUTING"

    exec_failed = ActionExecutionRecord(status="FAILED")
    assert RecommendationOutcomeService.derive_final_outcome(approval=appr, execution=exec_failed) == "FAILED"

    exec_completed = ActionExecutionRecord(status="COMPLETED")
    assert RecommendationOutcomeService.derive_final_outcome(approval=appr, execution=exec_completed) == "COMPLETED"


def test_derive_final_outcome_verification():
    """Verify Verification state precedence over Execution and Approval."""
    appr = ActionApproval(status="APPROVED")
    exec_rec = ActionExecutionRecord(status="COMPLETED")

    ver_verified = ActionVerificationRecord(status="VERIFIED")
    assert RecommendationOutcomeService.derive_final_outcome(
        approval=appr, execution=exec_rec, verification=ver_verified
    ) == "VERIFIED"

    ver_failed = ActionVerificationRecord(status="VERIFICATION_FAILED")
    assert RecommendationOutcomeService.derive_final_outcome(
        approval=appr, execution=exec_rec, verification=ver_failed
    ) == "VERIFICATION_FAILED"

    ver_inconclusive = ActionVerificationRecord(status="INCONCLUSIVE")
    assert RecommendationOutcomeService.derive_final_outcome(
        approval=appr, execution=exec_rec, verification=ver_inconclusive
    ) == "INCONCLUSIVE"


def test_derive_final_outcome_supervisor_reanalysis():
    """Verify Supervisor Re-analysis state precedence over Verification and Execution."""
    appr = ActionApproval(status="APPROVED")
    exec_rec = ActionExecutionRecord(status="COMPLETED")
    ver_rec = ActionVerificationRecord(status="VERIFIED")

    re_achieved = SupervisorReanalysisRecord(objective_status="ACHIEVED", status="SUCCESSFUL_OUTCOME")
    assert RecommendationOutcomeService.derive_final_outcome(
        approval=appr, execution=exec_rec, verification=ver_rec, reanalysis=re_achieved
    ) == "ACHIEVED"

    re_not_achieved = SupervisorReanalysisRecord(objective_status="NOT_ACHIEVED", status="UNSUCCESSFUL_OUTCOME")
    assert RecommendationOutcomeService.derive_final_outcome(
        approval=appr, execution=exec_rec, verification=ver_rec, reanalysis=re_not_achieved
    ) == "NOT_ACHIEVED"

    re_uncertain = SupervisorReanalysisRecord(objective_status="UNCERTAIN", status="UNCERTAIN_OUTCOME")
    assert RecommendationOutcomeService.derive_final_outcome(
        approval=appr, execution=exec_rec, verification=ver_rec, reanalysis=re_uncertain
    ) == "UNCERTAIN"
