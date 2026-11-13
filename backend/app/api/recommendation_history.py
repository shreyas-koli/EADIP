"""
API router for Recommendation Outcome History (R1).

Provides authenticated read-only endpoints for querying recommendation lifecycle history.

CRITICAL SECURITY GUARANTEES:
- Enforces user authentication and warehouse ownership.
- Prevents cross-warehouse and cross-tenant history access.
- Read-only queries only: NEVER modifies recommendation agent decision logic or warehouse state.
- Never returns database credentials or raw sensitive warehouse contents.
"""

from typing import Optional
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.auth import oauth2_scheme
from app.auth.service import get_current_user
from app.database.session import DBSession
from app.models.user import User
from app.schemas.recommendation_history import (
    CurrentConditionResponse,
    HistoricalMatchSummaryResponse,
    RecommendationDecisionBatchResponse,
    RecommendationDecisionResponse,
    RecommendationExplanationResponse,
    RecommendationHistoryListResponse,
    RecommendationOutcomeResponse,
)
from app.services.current_condition_service import CurrentConditionService
from app.services.recommendation_decision_service import RecommendationDecisionService
from app.services.recommendation_explanation_service import RecommendationExplanationService
from app.services.recommendation_outcome_service import RecommendationOutcomeService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/warehouses",
    tags=["Recommendation History"],
)


@router.get(
    "/{warehouse_id}/recommendation-history",
    response_model=RecommendationHistoryListResponse,
    status_code=status.HTTP_200_OK,
    summary="Get recommendation outcome history for a warehouse",
)
def get_recommendation_history(
    warehouse_id: int,
    db: DBSession,
    session_id: Optional[str] = Query(None, description="Filter by discovery session string ID"),
    outcome: Optional[str] = Query(None, description="Filter by final outcome status"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    token: str = Depends(oauth2_scheme),
):
    """
    Retrieve historical recommendation outcome records for a warehouse with authorization.
    """
    user: User = get_current_user(db, token)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        records = RecommendationOutcomeService.get_warehouse_history(
            db=db,
            warehouse_id=warehouse_id,
            user=user,
            session_id=session_id,
            final_outcome=outcome,
            limit=limit,
            offset=offset,
        )
        items = [RecommendationOutcomeResponse.model_validate(rec) for rec in records]
        return RecommendationHistoryListResponse(
            items=items,
            total=len(items),
            limit=limit,
            offset=offset,
        )
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        )
    except Exception as exc:
        db.rollback()
        logger.error(f"Error fetching recommendation history for warehouse {warehouse_id}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error retrieving recommendation history.",
        )


@router.get(
    "/{warehouse_id}/recommendation-history/sessions/{session_id}/actions/{action_id}",
    response_model=RecommendationOutcomeResponse,
    status_code=status.HTTP_200_OK,
    summary="Get recommendation outcome history for a specific action",
)
def get_action_recommendation_outcome(
    warehouse_id: int,
    session_id: str,
    action_id: str,
    db: DBSession,
    token: str = Depends(oauth2_scheme),
):
    """
    Retrieve the single historical recommendation outcome record for an action plan.
    """
    user: User = get_current_user(db, token)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        rec = RecommendationOutcomeService.get_action_outcome(
            db=db,
            warehouse_id=warehouse_id,
            session_id=session_id,
            action_id=action_id,
            user=user,
        )
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except Exception as exc:
        logger.error(f"Error fetching recommendation outcome for action '{action_id}': {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error retrieving recommendation outcome.",
        )

    if rec is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No outcome history record found for action '{action_id}' in session '{session_id}'.",
        )

    return RecommendationOutcomeResponse.model_validate(rec)


@router.get(
    "/{warehouse_id}/recommendation-history/matches",
    response_model=HistoricalMatchSummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Query historical matches for a candidate recommendation by structural fingerprint (R2)",
)
def get_recommendation_matches(
    warehouse_id: int,
    db: DBSession,
    fingerprint: Optional[str] = Query(None, description="Pre-computed SHA-256 fingerprint"),
    action_type: Optional[str] = Query(None, description="Action type (e.g. CREATE_INDEX, ANALYZE_TABLE)"),
    schema_name: Optional[str] = Query("public", alias="schema", description="Target schema name"),
    table_name: Optional[str] = Query(None, alias="table", description="Target table name"),
    column_name: Optional[str] = Query(None, alias="column", description="Target column name"),
    limit: int = Query(50, ge=1, le=100),
    token: str = Depends(oauth2_scheme),
):
    """
    Query historical recommendation outcome matches using SHA-256 structural fingerprinting.

    CRITICAL SCOPE RESTRICTION (R2):
    - Identity/matching ONLY.
    - Does NOT perform recommendation suppression or blocking.
    """
    user: User = get_current_user(db, token)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    from app.warehouse.service import get_warehouse_by_id
    warehouse = get_warehouse_by_id(db, warehouse_id, user)
    if warehouse is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Warehouse {warehouse_id} not found or access denied for user.",
        )

    from app.services.recommendation_fingerprint_service import RecommendationFingerprintService

    if not fingerprint and action_type:
        candidate = {
            "action_type": action_type,
            "schema": schema_name,
            "table": table_name,
            "column": column_name,
        }
        fingerprint = RecommendationFingerprintService.fingerprint_recommendation(candidate)

    if not fingerprint:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must specify either 'fingerprint' or candidate parameters ('action_type', 'table').",
        )

    summary = RecommendationFingerprintService.find_matches_for_candidate(
        db=db,
        warehouse_id=warehouse_id,
        candidate={
            "fingerprint": fingerprint,
            "action_type": action_type or "",
            "schema": schema_name,
            "table": table_name,
            "column": column_name,
        },
        limit=limit,
    )

    return HistoricalMatchSummaryResponse(
        fingerprint=summary["fingerprint"],
        match_found=summary["match_found"],
        match_count=summary["match_count"],
        matches=[RecommendationOutcomeResponse.model_validate(m) for m in RecommendationFingerprintService.find_historical_matches(db, warehouse_id, fingerprint, limit)],
    )


@router.get(
    "/{warehouse_id}/recommendation-history/conditions",
    response_model=CurrentConditionResponse,
    status_code=status.HTTP_200_OK,
    summary="Evaluate current warehouse condition for a recommendation candidate (R3)",
)
def evaluate_recommendation_condition(
    warehouse_id: int,
    db: DBSession,
    action_type: str = Query(..., description="Action type (e.g. ANALYZE_TABLE, CREATE_INDEX)"),
    schema_name: Optional[str] = Query("public", alias="schema", description="Target schema name"),
    table_name: Optional[str] = Query(None, alias="table", description="Target table name"),
    column_name: Optional[str] = Query(None, alias="column", description="Target column name"),
    recommendation_id: Optional[str] = Query(None, description="Optional recommendation ID"),
    token: str = Depends(oauth2_scheme),
):
    """
    Evaluate whether the underlying condition for a candidate recommendation currently exists in the warehouse.

    CRITICAL SCOPE RESTRICTION (R3):
    - Observational read-only catalog query.
    - Does NOT alter recommendation agent decision logic or suppress candidates.
    - Never exposes warehouse credentials or raw row contents.
    """
    user: User = get_current_user(db, token)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    candidate = {
        "recommendation_id": recommendation_id or "rec_query",
        "action_type": action_type,
        "schema": schema_name or "public",
        "table": table_name or "",
        "column": column_name,
    }

    try:
        result = CurrentConditionService.evaluate_candidate_condition(
            db=db,
            warehouse_id=warehouse_id,
            candidate=candidate,
            user=user,
        )
        return CurrentConditionResponse.model_validate(result)
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        )
    except Exception as exc:
        logger.error(f"Error evaluating current condition for warehouse {warehouse_id}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error evaluating current recommendation condition.",
        )


@router.post(
    "/{warehouse_id}/recommendations/decide",
    response_model=RecommendationDecisionResponse,
    status_code=status.HTTP_200_OK,
    summary="Evaluate recommendation decision for a candidate (R4)",
)
def evaluate_recommendation_decision(
    warehouse_id: int,
    candidate: dict,
    db: DBSession,
    token: str = Depends(oauth2_scheme),
):
    """
    Evaluate deterministic R4 recommendation lifecycle decision (PROPOSE / SUPPRESS / REVIEW)
    by combining R1 history, R2 fingerprint, and R3 current condition.

    CRITICAL SCOPE RESTRICTION (R4):
    - NO warehouse mutations.
    - NO automatic execution or approval bypassing.
    - Deterministic policy engine evaluation only.
    """
    user: User = get_current_user(db, token)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        result = RecommendationDecisionService.evaluate_candidate_decision(
            db=db,
            warehouse_id=warehouse_id,
            candidate=candidate,
            user=user,
        )
        return RecommendationDecisionResponse.model_validate(result)
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        )
    except Exception as exc:
        logger.error(f"Error evaluating R4 decision for warehouse {warehouse_id}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error evaluating recommendation decision.",
        )


@router.post(
    "/{warehouse_id}/recommendations/explain",
    response_model=RecommendationExplanationResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate deterministic recommendation audit explanation (R6)",
)
def get_recommendation_explanation(
    warehouse_id: int,
    candidate: dict,
    db: DBSession,
    token: str = Depends(oauth2_scheme),
):
    """
    Generate a structured, deterministic audit explanation (R6) explaining:
    - Why a recommendation was PROPOSED, SUPPRESSED, or placed in REVIEW.
    - Historical lifecycle state considered (R1/R2).
    - Current warehouse condition observed (R3).
    - R4 decision rule applied.
    - R5 lifecycle state transition.
    - Explicit evidence and uncertainty disclosures.

    CRITICAL SCOPE RESTRICTION (R6):
    - NO LLM calls or free-form hallucination.
    - NO warehouse mutations.
    - Template-based, auditable, deterministic reasoning only.
    """
    user: User = get_current_user(db, token)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        explanation = RecommendationExplanationService.get_candidate_explanation(
            db=db,
            warehouse_id=warehouse_id,
            candidate=candidate,
            user=user,
        )
        return RecommendationExplanationResponse.model_validate(explanation)
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        )
    except Exception as exc:
        logger.error(f"Error generating R6 explanation for warehouse {warehouse_id}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error generating recommendation explanation.",
        )


@router.get(
    "/{warehouse_id}/recommendations/{recommendation_id}/explanation",
    response_model=RecommendationExplanationResponse,
    status_code=status.HTTP_200_OK,
    summary="Get persistent recommendation audit explanation (R6.1)",
)
def get_recommendation_explanation_by_id(
    warehouse_id: int,
    recommendation_id: str,
    db: DBSession,
    session_id: Optional[int] = Query(None, description="Optional discovery session ID for historical record lookup"),
    action_type: Optional[str] = Query(None, description="Action type (e.g. ANALYZE_TABLE, CREATE_INDEX)"),
    schema_name: Optional[str] = Query("public", alias="schema", description="Target schema name"),
    table_name: Optional[str] = Query(None, alias="table", description="Target table name"),
    column_name: Optional[str] = Query(None, alias="column", description="Target column name"),
    token: str = Depends(oauth2_scheme),
):
    """
    Retrieve structured R6 audit explanation for a recommendation.
    Prefers durable historical database record if session_id is provided or present in DB.
    """
    user: User = get_current_user(db, token)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        # 1. First attempt durable historical record lookup from DB
        historical = RecommendationExplanationService.get_historical_explanation(
            db=db,
            warehouse_id=warehouse_id,
            recommendation_id=recommendation_id,
            user=user,
            session_id=session_id,
        )
        if historical:
            return RecommendationExplanationResponse.model_validate(historical)

        if not action_type:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No persisted explanation record found for recommendation '{recommendation_id}'. Specify 'action_type' to generate live evaluation.",
            )

        candidate = {
            "recommendation_id": recommendation_id,
            "action_type": action_type,
            "schema": schema_name or "public",
            "table": table_name or "",
            "column": column_name,
            "session_id": session_id,
        }

        explanation = RecommendationExplanationService.get_candidate_explanation(
            db=db,
            warehouse_id=warehouse_id,
            candidate=candidate,
            user=user,
            session_id=session_id,
        )
        return RecommendationExplanationResponse.model_validate(explanation)
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Error retrieving R6 explanation for recommendation '{recommendation_id}': {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error retrieving recommendation explanation.",
        )



