"""
Recommendation Fingerprinting & Structural Deduplication Service (R2).

Computes deterministic, action-type-specific cryptographic fingerprints (SHA-256)
to identify structural equivalence between recommendation candidates across discovery sessions.

CRITICAL SCOPE RESTRICTIONS (R2):
- Identity & comparison ONLY.
- Does NOT alter Recommendation Agent decision logic.
- Does NOT suppress, block, or automatically remove recommendations.
- Fingerprint match != recommendation suppression!
"""

import hashlib
import json
import logging
from typing import Any, Dict, List, Optional, Union

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.recommendation_outcome_record import RecommendationOutcomeRecord

logger = logging.getLogger(__name__)


class RecommendationFingerprintService:
    """
    Service for building canonical payloads, generating SHA-256 fingerprints,
    and querying structural outcome history.
    """

    @classmethod
    def build_canonical_payload(
        cls,
        action_type: str,
        target: Optional[Dict[str, Any]] = None,
        parameters: Optional[Dict[str, Any]] = None,
        schema: Optional[str] = None,
        table: Optional[str] = None,
        column: Optional[Union[str, List[str]]] = None,
    ) -> Dict[str, Any]:
        """
        Construct a normalized, deterministic canonical payload dictionary.

        Excludes all volatile attributes (IDs, timestamps, execution statements, confidence scores, human descriptions).
        """
        # 1. Normalize action type
        raw_type = action_type or "UNKNOWN"
        norm_type = raw_type.strip().upper()

        # 2. Extract and normalize schema
        raw_schema = (
            schema
            or (target.get("schema") if target else None)
            or (parameters.get("schema") if parameters else None)
            or "public"
        )
        norm_schema = str(raw_schema).strip().lower()

        # 3. Extract and normalize table
        raw_table = (
            table
            or (target.get("table") if target else None)
            or (parameters.get("table") if parameters else None)
            or ""
        )
        norm_table = str(raw_table).strip().lower()

        # 4. Extract and normalize column(s)
        raw_col = (
            column
            or (target.get("column") if target else None)
            or (target.get("columns") if target else None)
            or (parameters.get("column") if parameters else None)
            or (parameters.get("columns") if parameters else None)
        )

        norm_column: Optional[Union[str, List[str]]] = None
        if isinstance(raw_col, list):
            norm_column = sorted([str(c).strip().lower() for c in raw_col if c])
        elif isinstance(raw_col, str) and raw_col.strip():
            norm_column = raw_col.strip().lower()

        # 5. Build canonical target structure
        canonical_target: Dict[str, Any] = {
            "schema": norm_schema,
            "table": norm_table,
        }

        if norm_column is not None:
            if isinstance(norm_column, list):
                canonical_target["columns"] = norm_column
            else:
                canonical_target["column"] = norm_column

        # Include additional non-volatile structural properties if present
        if parameters:
            for k in ("index_type", "constraint_type"):
                if k in parameters and parameters[k]:
                    canonical_target[k] = str(parameters[k]).strip().lower()

        return {
            "action_type": norm_type,
            "target": canonical_target,
        }

    @classmethod
    def generate_fingerprint(
        cls,
        action_type: str,
        target: Optional[Dict[str, Any]] = None,
        parameters: Optional[Dict[str, Any]] = None,
        schema: Optional[str] = None,
        table: Optional[str] = None,
        column: Optional[Union[str, List[str]]] = None,
    ) -> str:
        """
        Generate a 64-character SHA-256 fingerprint string from candidate attributes.
        """
        canonical_payload = cls.build_canonical_payload(
            action_type=action_type,
            target=target,
            parameters=parameters,
            schema=schema,
            table=table,
            column=column,
        )
        json_str = json.dumps(canonical_payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(json_str.encode("utf-8")).hexdigest()

    @classmethod
    def fingerprint_recommendation(cls, item: Dict[str, Any]) -> str:
        """
        Extract target fields from a recommendation or action plan dictionary and return SHA-256 fingerprint.
        """
        action_type = (
            item.get("action_type")
            or item.get("recommendation_type")
            or item.get("type")
            or "UNKNOWN"
        )
        target = item.get("target") if isinstance(item.get("target"), dict) else None
        parameters = item.get("parameters") if isinstance(item.get("parameters"), dict) else None
        schema = item.get("schema")
        table = item.get("table")
        column = item.get("column")

        return cls.generate_fingerprint(
            action_type=action_type,
            target=target,
            parameters=parameters,
            schema=schema,
            table=table,
            column=column,
        )

    @classmethod
    def find_historical_matches(
        cls,
        db: Session,
        warehouse_id: int,
        fingerprint: str,
        limit: int = 50,
    ) -> List[RecommendationOutcomeRecord]:
        """
        Query historical RecommendationOutcomeRecords for a warehouse matching the candidate fingerprint.
        """
        if not fingerprint:
            return []

        stmt = select(RecommendationOutcomeRecord).where(
            RecommendationOutcomeRecord.warehouse_id == warehouse_id,
            RecommendationOutcomeRecord.fingerprint == fingerprint,
        ).order_by(RecommendationOutcomeRecord.updated_at.desc()).limit(limit)

        return list(db.execute(stmt).scalars().all())

    @classmethod
    def find_matches_for_candidate(
        cls,
        db: Session,
        warehouse_id: int,
        candidate: Dict[str, Any],
        limit: int = 50,
    ) -> Dict[str, Any]:
        """
        Calculate fingerprint for candidate recommendation and return historical match summary.

        CRITICAL R2 SCOPE Assertion: Does NOT perform suppression.
        """
        fingerprint = cls.fingerprint_recommendation(candidate)
        matches = cls.find_historical_matches(db, warehouse_id, fingerprint, limit=limit)

        formatted_matches = [
            {
                "id": m.id,
                "recommendation_id": m.recommendation_id,
                "action_id": m.action_id,
                "session_id": m.session_id,
                "action_type": m.action_type,
                "approval_status": m.approval_status,
                "execution_status": m.execution_status,
                "verification_status": m.verification_status,
                "objective_status": m.objective_status,
                "final_outcome": m.final_outcome,
                "updated_at": m.updated_at.isoformat() if m.updated_at else None,
            }
            for m in matches
        ]

        return {
            "fingerprint": fingerprint,
            "match_found": len(matches) > 0,
            "match_count": len(matches),
            "matches": formatted_matches,
        }
