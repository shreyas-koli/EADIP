"""
Recommendation outcome record ORM model (R1: Recommendation Outcome History).

Stores canonical historical records tracking the complete lifecycle of warehouse recommendations
from initial proposal through approval, execution, verification, supervisor re-analysis, and final outcome.

CRITICAL SCOPE RESTRICTION (R1):
- History ONLY.
- Does NOT alter Recommendation Agent decision logic or suppress/block recommendations.
- Does NOT store credentials, connection strings, database passwords, or raw sensitive customer data.
"""

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func, JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class RecommendationOutcomeRecord(Base):
    """
    ``recommendation_outcome_records`` table - stores historical lifecycle outcomes for
    discovery session recommendations and action plans.

    Attributes
    ──────────
    id                      Auto-incrementing primary key.
    recommendation_id       String ID of recommendation / action plan.
    action_id               String ID of the action plan within session.
    session_id              Foreign key to discovery session.
    warehouse_id            Foreign key to target warehouse.
    user_id                 Foreign key to user (optional, if user-triggered action).
    action_type             Action classification (e.g., 'CREATE_INDEX', 'ANALYZE_TABLE').
    target                  JSON snapshot of target schema/table/column.
    approval_id             Foreign key to ActionApproval (optional).
    execution_id            Foreign key to ActionExecutionRecord (optional).
    verification_id         Foreign key to ActionVerificationRecord (optional).
    reanalysis_id           Foreign key to SupervisorReanalysisRecord (optional).
    approval_status         Status of user approval ('PROPOSED', 'APPROVED', 'REJECTED').
    execution_status        Status of execution ('PENDING', 'EXECUTING', 'COMPLETED', 'FAILED').
    verification_status     Status of verification ('PENDING', 'VERIFIED', 'VERIFICATION_FAILED', 'INCONCLUSIVE').
    reanalysis_status       Status of supervisor re-analysis ('PENDING', 'SUCCESSFUL_OUTCOME', 'UNSUCCESSFUL_OUTCOME', 'UNCERTAIN_OUTCOME').
    objective_status        Supervisor objective status ('PENDING', 'ACHIEVED', 'NOT_ACHIEVED', 'UNCERTAIN').
    final_outcome           Authoritative derived outcome ('PROPOSED', 'APPROVED', 'REJECTED', 'EXECUTING', 'COMPLETED', 'FAILED', 'VERIFIED', 'VERIFICATION_FAILED', 'INCONCLUSIVE', 'ACHIEVED', 'NOT_ACHIEVED', 'UNCERTAIN').
    created_at              Timestamp of initial recording.
    updated_at              Timestamp of latest state transition.
    """

    __tablename__ = "recommendation_outcome_records"

    __table_args__ = (
        UniqueConstraint("action_id", "session_id", name="uq_rec_outcome_action_session"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    recommendation_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)

    action_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)

    session_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("discovery_sessions.id", ondelete="CASCADE"), index=True, nullable=False
    )

    warehouse_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("warehouses.id", ondelete="CASCADE"), index=True, nullable=False
    )

    user_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )

    action_type: Mapped[str] = mapped_column(String(100), nullable=False)

    target: Mapped[Optional[Any]] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=True)

    approval_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("action_approvals.id", ondelete="SET NULL"), index=True, nullable=True
    )

    execution_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("action_execution_records.id", ondelete="SET NULL"), index=True, nullable=True
    )

    verification_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("action_verification_records.id", ondelete="SET NULL"), index=True, nullable=True
    )

    reanalysis_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("supervisor_reanalysis_records.id", ondelete="SET NULL"), index=True, nullable=True
    )

    approval_status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, default="PROPOSED")

    execution_status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, default="PENDING")

    verification_status: Mapped[Optional[str]] = mapped_column(String(30), nullable=True, default="PENDING")

    reanalysis_status: Mapped[Optional[str]] = mapped_column(String(40), nullable=True, default="PENDING")

    objective_status: Mapped[Optional[str]] = mapped_column(String(30), nullable=True, default="PENDING")

    final_outcome: Mapped[str] = mapped_column(String(30), index=True, nullable=False, default="PROPOSED")

    fingerprint: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=func.now(), nullable=False
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )

    # ── Relationships ─────────────────────────────────────────────

    session: Mapped["DiscoverySession"] = relationship("DiscoverySession")  # noqa: F821
    warehouse: Mapped["Warehouse"] = relationship("Warehouse")  # noqa: F821
    user: Mapped[Optional["User"]] = relationship("User")  # noqa: F821
    approval: Mapped[Optional["ActionApproval"]] = relationship("ActionApproval")  # noqa: F821
    execution: Mapped[Optional["ActionExecutionRecord"]] = relationship("ActionExecutionRecord")  # noqa: F821
    verification: Mapped[Optional["ActionVerificationRecord"]] = relationship("ActionVerificationRecord")  # noqa: F821
    reanalysis: Mapped[Optional["SupervisorReanalysisRecord"]] = relationship("SupervisorReanalysisRecord")  # noqa: F821

    def __repr__(self) -> str:
        return (
            f"<RecommendationOutcomeRecord(id={self.id}, action_id={self.action_id!r}, "
            f"action_type={self.action_type!r}, final_outcome={self.final_outcome!r})>"
        )
