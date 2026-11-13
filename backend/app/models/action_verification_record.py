"""
Action verification record ORM model.

Stores verification attempts, checks performed, expected vs observed state,
evidence, and status for Phase 6 Controlled Verification Engine operations.
"""

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func, JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class ActionVerificationRecord(Base):
    """
    ``action_verification_records`` table - stores verification history of executed
    automation action plans against connected data warehouses.

    Attributes
    ──────────
    id                      Auto-incrementing primary key.
    verification_id         Unique string ID of the verification run.
    execution_id            Foreign key to the action execution record.
    action_id               String ID of the action plan.
    session_id              Foreign key to the discovery session.
    warehouse_id            Foreign key to the target warehouse.
    user_id                 Foreign key to the verifying user.
    status                  Verification status ('VERIFIED', 'VERIFICATION_FAILED', 'INCONCLUSIVE').
    verified                Boolean outcome (True if verified, False if failed, None if inconclusive).
    action_type             Type of action (e.g. 'CREATE_INDEX', 'ANALYZE_TABLE').
    target                  JSON snapshot of target schema/table/column.
    expected_state          JSON snapshot of expected warehouse state.
    observed_state          JSON snapshot of observed warehouse state.
    evidence                JSON list of evidence statements.
    checks                  JSON list of structured check results.
    duration_ms             Verification duration in milliseconds.
    error_message           Sanitized error message if verification error occurred.
    created_at              Timestamp when verification started.
    updated_at              Timestamp when verification completed.
    """

    __tablename__ = "action_verification_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    verification_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)

    execution_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("action_execution_records.id", ondelete="CASCADE"), index=True, nullable=False
    )

    action_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)

    session_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("discovery_sessions.id", ondelete="CASCADE"), index=True, nullable=False
    )

    warehouse_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("warehouses.id", ondelete="CASCADE"), index=True, nullable=False
    )

    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )

    status: Mapped[str] = mapped_column(String(30), nullable=False, default="INCONCLUSIVE")

    verified: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)

    action_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    target: Mapped[Optional[Any]] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=True)

    expected_state: Mapped[Optional[Any]] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=True)

    observed_state: Mapped[Optional[Any]] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=True)

    evidence: Mapped[Optional[Any]] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=True)

    checks: Mapped[Optional[Any]] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=True)

    duration_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

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
    session: Mapped["DiscoverySession"] = relationship("DiscoverySession")  # noqa: F821
    warehouse: Mapped["Warehouse"] = relationship("Warehouse")  # noqa: F821
    user: Mapped["User"] = relationship("User")  # noqa: F821

    def __repr__(self) -> str:
        return (
            f"<ActionVerificationRecord(id={self.id}, verification_id={self.verification_id!r}, "
            f"status={self.status!r}, verified={self.verified})>"
        )
