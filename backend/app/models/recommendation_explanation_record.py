"""
Recommendation explanation record ORM model (R6.1: Persistent Explanation Audit Records).

Stores durable, historically immutable audit records for recommendation explanations
generated during discovery evaluations.

CRITICAL GUARANTEES (R6.1):
- Historically Immutable: Once persisted for a session, decision-time facts are never overwritten.
- Multi-Session Isolation: Separate discovery sessions maintain separate explanation records.
- Zero Credentials: Does NOT store credentials, connection strings, or raw sensitive customer data.
"""

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func, JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class RecommendationExplanationRecord(Base):
    """
    ``recommendation_explanation_records`` table - stores durable, immutable R6 audit explanations
    and decision-time evidence snapshots.

    Attributes
    ──────────
    id                      Auto-incrementing primary key.
    recommendation_id       String ID of recommendation / action candidate.
    action_id               Optional action ID within session.
    session_id              Foreign key to discovery session.
    warehouse_id            Foreign key to target warehouse.
    action_type             Action classification (e.g., 'CREATE_INDEX', 'ANALYZE_TABLE').
    fingerprint             SHA-256 structural fingerprint string (R2).
    target                  JSON snapshot of target schema/table/column.
    decision                Policy decision ('PROPOSE', 'SUPPRESS', 'REVIEW').
    decision_reason_code    R4 decision rule identifier (e.g. 'CONDITION_REAPPEARED').
    decision_reason         Human readable decision rationale.
    lifecycle_state         R5 lifecycle state ('ACTIVE', 'SUPPRESSED', 'REVIEW', 'REOPENED').
    summary                 Deterministic human explanation summary string.
    historical_context      JSON snapshot of R1/R2 historical outcome context.
    current_condition       JSON snapshot of R3 observed catalog condition at decision time.
    decision_evidence       JSON list of R2-R4 decision evidence items.
    lifecycle_evidence      JSON list of R5 lifecycle transition evidence items.
    uncertainty             JSON snapshot of uncertainty disclosure details (nullable).
    created_at              Timestamp when explanation record was persisted.
    """

    __tablename__ = "recommendation_explanation_records"

    __table_args__ = (
        UniqueConstraint("session_id", "recommendation_id", name="uq_rec_exp_session_rec"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    recommendation_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)

    action_id: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True)

    session_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("discovery_sessions.id", ondelete="CASCADE"), index=True, nullable=False
    )

    warehouse_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("warehouses.id", ondelete="CASCADE"), index=True, nullable=False
    )

    action_type: Mapped[str] = mapped_column(String(100), nullable=False)

    fingerprint: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True)

    target: Mapped[Optional[Any]] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=True)

    decision: Mapped[str] = mapped_column(String(20), index=True, nullable=False)

    decision_reason_code: Mapped[str] = mapped_column(String(100), nullable=False)

    decision_reason: Mapped[str] = mapped_column(String(500), nullable=False)

    lifecycle_state: Mapped[str] = mapped_column(String(30), nullable=False)

    summary: Mapped[str] = mapped_column(String(1000), nullable=False)

    historical_context: Mapped[Optional[Any]] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=True)

    current_condition: Mapped[Optional[Any]] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=True)

    decision_evidence: Mapped[Optional[Any]] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=True)

    lifecycle_evidence: Mapped[Optional[Any]] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=True)

    uncertainty: Mapped[Optional[Any]] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=func.now(), nullable=False
    )

    # ── Relationships ─────────────────────────────────────────────

    session: Mapped["DiscoverySession"] = relationship("DiscoverySession")  # noqa: F821
    warehouse: Mapped["Warehouse"] = relationship("Warehouse")  # noqa: F821

    def __repr__(self) -> str:
        return (
            f"<RecommendationExplanationRecord(id={self.id}, recommendation_id={self.recommendation_id!r}, "
            f"session_id={self.session_id}, decision={self.decision!r}, lifecycle_state={self.lifecycle_state!r})>"
        )
