"""
Action execution record ORM model.

Stores execution attempts, duration, safe SQL statement fingerprints, safe error messages,
and verification state for Phase 5 Controlled Execution Engine operations.
"""

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func, JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class ActionExecutionRecord(Base):
    """
    ``action_execution_records`` table - stores execution history of approved
    automation action plans executed against connected data warehouses.

    Attributes
    ──────────
    id                      Auto-incrementing primary key.
    action_id               String ID of the action plan.
    approval_id             Foreign key to the action approval record.
    session_id              Foreign key to the discovery session.
    warehouse_id            Foreign key to the target warehouse.
    user_id                 Foreign key to the executing user.
    status                  Execution status ('EXECUTING', 'COMPLETED', 'FAILED').
    action_type             Type of action (e.g. 'CREATE_INDEX', 'ANALYZE_TABLE').
    target                  JSON snapshot of target schema/table/column.
    statement_fingerprint   Safe SQL statement executed.
    duration_ms             Execution duration in milliseconds.
    error_message           Sanitized error message if execution failed.
    verification_status     Verification state ('PENDING' in Phase 5).
    created_at              Timestamp when execution started.
    updated_at              Timestamp when execution state updated.
    """

    __tablename__ = "action_execution_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    action_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)

    approval_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("action_approvals.id", ondelete="SET NULL"), index=True, nullable=True
    )

    session_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("discovery_sessions.id", ondelete="CASCADE"), index=True, nullable=False
    )

    warehouse_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("warehouses.id", ondelete="CASCADE"), index=True, nullable=False
    )

    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="EXECUTING")

    action_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    target: Mapped[Optional[Any]] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=True)

    statement_fingerprint: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    duration_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    verification_status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING")

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

    approval: Mapped[Optional["ActionApproval"]] = relationship("ActionApproval")  # noqa: F821
    session: Mapped["DiscoverySession"] = relationship("DiscoverySession")  # noqa: F821
    warehouse: Mapped["Warehouse"] = relationship("Warehouse")  # noqa: F821
    user: Mapped["User"] = relationship("User")  # noqa: F821

    def __repr__(self) -> str:
        return (
            f"<ActionExecutionRecord(id={self.id}, action_id={self.action_id!r}, "
            f"status={self.status!r}, duration_ms={self.duration_ms})>"
        )
