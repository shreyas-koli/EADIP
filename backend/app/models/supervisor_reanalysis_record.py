"""
Supervisor re-analysis record ORM model.

Stores post-execution assessments, before vs after state comparisons, objective status,
findings, conclusions, and follow-up recommendations for Phase 7 operations.
"""

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func, JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class SupervisorReanalysisRecord(Base):
    """
    ``supervisor_reanalysis_records`` table - stores post-execution assessment results
    synthesized by the Supervisor Re-analysis engine.

    Attributes
    ──────────
    id                      Auto-incrementing primary key.
    reanalysis_id           Unique string ID of the re-analysis run.
    session_id              Foreign key to the discovery session.
    warehouse_id            Foreign key to the target warehouse.
    user_id                 Foreign key to the analyzing user.
    action_id               String ID of the action plan.
    execution_id            Foreign key to the action execution record.
    verification_id         Foreign key to the action verification record (if available).
    status                  Assessment status ('SUCCESSFUL_OUTCOME', 'UNSUCCESSFUL_OUTCOME',
                            'UNCERTAIN_OUTCOME', 'NO_FOLLOW_UP_REQUIRED', 'FOLLOW_UP_REQUIRED').
    objective_status        Objective outcome ('ACHIEVED', 'NOT_ACHIEVED', 'UNCERTAIN', 'NOT_APPLICABLE').
    before_state            JSON snapshot of warehouse state before action execution.
    after_state             JSON snapshot of warehouse state after action execution and verification.
    comparisons             JSON list of before vs after comparison metrics and evidence.
    findings                JSON list of observation finding strings.
    conclusion              Text summary of post-execution conclusions.
    follow_up_required      Boolean indicator if follow-up action/observation is recommended.
    follow_up_type          Follow-up classification ('NONE', 'OBSERVATION', 'ANALYSIS', 'RECOMMENDATION').
    follow_up_details       JSON payload of recommended follow-up action plan (in PROPOSED state).
    duration_ms             Re-analysis duration in milliseconds.
    created_at              Timestamp when re-analysis started.
    updated_at              Timestamp when re-analysis completed.
    """

    __tablename__ = "supervisor_reanalysis_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    reanalysis_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)

    session_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("discovery_sessions.id", ondelete="CASCADE"), index=True, nullable=False
    )

    warehouse_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("warehouses.id", ondelete="CASCADE"), index=True, nullable=False
    )

    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )

    action_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)

    execution_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("action_execution_records.id", ondelete="CASCADE"), index=True, nullable=False
    )

    verification_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("action_verification_records.id", ondelete="SET NULL"), index=True, nullable=True
    )

    status: Mapped[str] = mapped_column(String(40), nullable=False, default="UNCERTAIN_OUTCOME")

    objective_status: Mapped[str] = mapped_column(String(30), nullable=False, default="UNCERTAIN")

    before_state: Mapped[Optional[Any]] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=True)

    after_state: Mapped[Optional[Any]] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=True)

    comparisons: Mapped[Optional[Any]] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=True)

    findings: Mapped[Optional[Any]] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=True)

    conclusion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    follow_up_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    follow_up_type: Mapped[str] = mapped_column(String(30), nullable=False, default="NONE")

    follow_up_details: Mapped[Optional[Any]] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=True)

    duration_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

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

    execution: Mapped["ActionExecutionRecord"] = relationship("ActionExecutionRecord")  # noqa: F821
    verification: Mapped[Optional["ActionVerificationRecord"]] = relationship("ActionVerificationRecord")  # noqa: F821
    session: Mapped["DiscoverySession"] = relationship("DiscoverySession")  # noqa: F821
    warehouse: Mapped["Warehouse"] = relationship("Warehouse")  # noqa: F821
    user: Mapped["User"] = relationship("User")  # noqa: F821

    def __repr__(self) -> str:
        return (
            f"<SupervisorReanalysisRecord(id={self.id}, reanalysis_id={self.reanalysis_id!r}, "
            f"objective_status={self.objective_status!r}, follow_up_required={self.follow_up_required})>"
        )
