"""
Warehouse automation & user approval API endpoints.

Handles listing proposed action plans and recording human-in-the-loop decisions (APPROVE / REJECT).
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from app.api.auth import oauth2_scheme
from app.auth.service import get_current_user
from app.database.session import DBSession
from app.schemas.automation import (
    ActionPlanDetail,
    ApprovalRequest,
    ApprovalResponse,
    ExecutionResultResponse,
    VerificationResultResponse,
    SupervisorReanalysisResponse,
)
from app.services.automation_service import AutomationService
from app.services.action_execution_service import ActionExecutionService
from app.services.action_verification_service import ActionVerificationService
from app.services.action_reanalysis_service import ActionReanalysisService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/warehouses",
    tags=["Automation"],
)


@router.post(
    "/{warehouse_id}/automation/sessions/{session_id}/actions/{action_id}/reanalyze",
    response_model=SupervisorReanalysisResponse,
    status_code=status.HTTP_200_OK,
    summary="Synthesize post-execution supervisor re-analysis",
)
def reanalyze_action_plan(
    warehouse_id: int,
    session_id: str,
    action_id: str,
    db: DBSession,
    token: str = Depends(oauth2_scheme),
):
    """
    Synthesize post-execution assessment comparing pre-execution state,
    execution metrics, and verification catalog evidence.

    Does NOT execute automatic remediation, automatic rollback, or automatic retries.
    Follow-up actions enter status 'PROPOSED' requiring explicit user approval.
    """
    user = get_current_user(db, token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        response = ActionReanalysisService.reanalyze_action(
            db=db,
            warehouse_id=warehouse_id,
            session_id=session_id,
            action_id=action_id,
            user=user,
        )
        return response
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except Exception as exc:
        logger.error(f"Error re-analyzing action '{action_id}': {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to perform supervisor re-analysis.",
        )


@router.get(
    "/{warehouse_id}/automation/sessions/{session_id}/actions/{action_id}/reanalysis",
    response_model=Optional[SupervisorReanalysisResponse],
    status_code=status.HTTP_200_OK,
    summary="Get supervisor re-analysis details for an action plan",
)
def get_action_reanalysis_result(
    warehouse_id: int,
    session_id: str,
    action_id: str,
    db: DBSession,
    token: str = Depends(oauth2_scheme),
):
    """
    Retrieve existing supervisor re-analysis details for an action plan.
    """
    user = get_current_user(db, token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        response = ActionReanalysisService.get_reanalysis_result(
            db=db,
            warehouse_id=warehouse_id,
            session_id=session_id,
            action_id=action_id,
            user=user,
        )
        return response
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except Exception as exc:
        logger.error(f"Error fetching re-analysis details for action '{action_id}': {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve supervisor re-analysis details.",
        )


@router.post(
    "/{warehouse_id}/automation/sessions/{session_id}/actions/{action_id}/verify",
    response_model=VerificationResultResponse,
    status_code=status.HTTP_200_OK,
    summary="Verify an executed action plan",
)
def verify_action_plan(
    warehouse_id: int,
    session_id: str,
    action_id: str,
    db: DBSession,
    token: str = Depends(oauth2_scheme),
):
    """
    Perform evidence-based read-only catalog verification for an executed action plan.

    Re-validates user authorization, warehouse ownership, and execution completion
    (requires an ActionExecutionRecord with status 'COMPLETED') before executing
    read-only catalog queries.
    """
    user = get_current_user(db, token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        response = ActionVerificationService.verify_action(
            db=db,
            warehouse_id=warehouse_id,
            session_id=session_id,
            action_id=action_id,
            user=user,
        )
        return response
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except Exception as exc:
        logger.error(f"Error verifying action '{action_id}': {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to verify action plan.",
        )


@router.get(
    "/{warehouse_id}/automation/sessions/{session_id}/actions/{action_id}/verification",
    response_model=Optional[VerificationResultResponse],
    status_code=status.HTTP_200_OK,
    summary="Get verification details for an action plan",
)
def get_action_verification_result(
    warehouse_id: int,
    session_id: str,
    action_id: str,
    db: DBSession,
    token: str = Depends(oauth2_scheme),
):
    """
    Retrieve existing verification details for an executed action plan.
    """
    user = get_current_user(db, token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        response = ActionVerificationService.get_verification_result(
            db=db,
            warehouse_id=warehouse_id,
            session_id=session_id,
            action_id=action_id,
            user=user,
        )
        return response
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except Exception as exc:
        logger.error(f"Error fetching verification details for action '{action_id}': {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve verification details.",
        )


@router.post(
    "/{warehouse_id}/automation/sessions/{session_id}/actions/{action_id}/execute",
    response_model=ExecutionResultResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute an approved action plan",
)
def execute_action_plan(
    warehouse_id: int,
    session_id: str,
    action_id: str,
    db: DBSession,
    token: str = Depends(oauth2_scheme),
):
    """
    Execute an approved action plan against the target data warehouse.

    Re-validates user authorization, warehouse ownership, DB approval state,
    and parameter integrity before invoking the Controlled Execution Engine.
    """
    user = get_current_user(db, token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        response = ActionExecutionService.execute_action(
            db=db,
            warehouse_id=warehouse_id,
            session_id=session_id,
            action_id=action_id,
            user=user,
        )
        return response
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except Exception as exc:
        db.rollback()
        logger.error(f"Error executing action '{action_id}': {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to execute action plan: {str(exc)}",
        )


@router.get(
    "/{warehouse_id}/automation/sessions/{session_id}/actions",
    response_model=List[ActionPlanDetail],
    summary="List action plans for a discovery session",
)
def get_session_action_plans(
    warehouse_id: int,
    session_id: str,
    db: DBSession,
    token: str = Depends(oauth2_scheme),
):
    """
    Retrieve all proposed action plans generated by the Automation Agent
    for a specific discovery session, along with their current approval status.
    """
    user = get_current_user(db, token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        actions = AutomationService.get_action_plans(
            db=db,
            warehouse_id=warehouse_id,
            session_id=session_id,
            user=user,
        )
        return actions
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except Exception as exc:
        logger.error(f"Error listing action plans: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve action plans.",
        )


@router.post(
    "/{warehouse_id}/automation/sessions/{session_id}/actions/{action_id}/approve",
    response_model=ApprovalResponse,
    status_code=status.HTTP_200_OK,
    summary="Approve a proposed action plan",
)
def approve_action_plan(
    warehouse_id: int,
    session_id: str,
    action_id: str,
    db: DBSession,
    payload: Optional[ApprovalRequest] = None,
    token: str = Depends(oauth2_scheme),
):
    """
    Record user approval for a proposed action plan.

    Updates the action status to ``APPROVED`` and creates an audit record.
    Does **NOT** execute any SQL or modify the warehouse.
    """
    user = get_current_user(db, token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        response = AutomationService.approve_action(
            db=db,
            warehouse_id=warehouse_id,
            session_id=session_id,
            action_id=action_id,
            user=user,
            payload=payload,
        )
        return response
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except Exception as exc:
        logger.error(f"Error approving action '{action_id}': {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to record action approval.",
        )


@router.post(
    "/{warehouse_id}/automation/sessions/{session_id}/actions/{action_id}/reject",
    response_model=ApprovalResponse,
    status_code=status.HTTP_200_OK,
    summary="Reject a proposed action plan",
)
def reject_action_plan(
    warehouse_id: int,
    session_id: str,
    action_id: str,
    db: DBSession,
    payload: Optional[ApprovalRequest] = None,
    token: str = Depends(oauth2_scheme),
):
    """
    Record user rejection for a proposed action plan.

    Updates the action status to ``REJECTED`` and stores optional rejection reason.
    Does **NOT** execute any SQL or modify the warehouse.
    """
    user = get_current_user(db, token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        response = AutomationService.reject_action(
            db=db,
            warehouse_id=warehouse_id,
            session_id=session_id,
            action_id=action_id,
            user=user,
            payload=payload,
        )
        return response
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except Exception as exc:
        logger.error(f"Error rejecting action '{action_id}': {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to record action rejection.",
        )
