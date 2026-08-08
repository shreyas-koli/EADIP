"""
Execution history ORM models.

Represents the execution history of discovery sessions and the individual
agent executions within those sessions.
"""

from datetime import datetime
from typing import Any, List, Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func, JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class DiscoverySession(Base):
    """
    ``discovery_sessions`` table - stores one complete discovery execution
    for a warehouse.

    Attributes
    ──────────
    id                  Auto-incrementing primary key.
    session_id          Unique string identifying the session.
    warehouse_id        Foreign key to the warehouse.
    started_at          When the discovery session started.
    finished_at         When the discovery session finished.
    total_duration_ms   Total duration in milliseconds.
    status              Final status (RUNNING, COMPLETED, FAILED).
    recommendations     JSONB snapshot of the final recommendations.
    created_at          Row creation timestamp.
    """

    __tablename__ = "discovery_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    session_id: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    
    warehouse_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("warehouses.id"), index=True, nullable=False
    )
    
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    total_duration_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    
    recommendations: Mapped[Optional[Any]] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # ── Relationships ─────────────────────────────────────────────
    
    agent_executions: Mapped[List["AgentExecution"]] = relationship(
        "AgentExecution",
        back_populates="session",
        cascade="all, delete-orphan",
    )
    
    # Optional representation for easier debugging
    def __repr__(self) -> str:
        return (
            f"<DiscoverySession(id={self.id}, session_id={self.session_id!r}, "
            f"warehouse_id={self.warehouse_id}, status={self.status!r})>"
        )


class AgentExecution(Base):
    """
    ``agent_executions`` table - stores one agent execution belonging to
    a discovery session.

    Attributes
    ──────────
    id                  Auto-incrementing primary key.
    session_id          Foreign key to the discovery session.
    agent_name          Name of the agent (e.g., 'metadata', 'security').
    status              Final status (RUNNING, COMPLETED, FAILED, SKIPPED).
    started_at          When the agent started.
    finished_at         When the agent finished.
    duration_ms         Execution duration in milliseconds.
    wave                The execution wave number.
    error               Optional error message if the agent failed.
    """

    __tablename__ = "agent_executions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    session_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("discovery_sessions.id"), index=True, nullable=False
    )
    
    agent_name: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    duration_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    wave: Mapped[int] = mapped_column(Integer, nullable=False)
    
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ── Relationships ─────────────────────────────────────────────
    
    session: Mapped["DiscoverySession"] = relationship(
        "DiscoverySession",
        back_populates="agent_executions"
    )

    def __repr__(self) -> str:
        return (
            f"<AgentExecution(id={self.id}, agent_name={self.agent_name!r}, "
            f"status={self.status!r})>"
        )
