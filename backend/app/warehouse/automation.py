"""
Warehouse automation engine.

Transforms approved-type recommendations produced by the Recommendation Agent
into **safe, structured, executable action plans** for a future approval and
execution pipeline.

Critical scope constraints (Phase 3):
- This engine does **NOT** execute any SQL.
- This engine does **NOT** modify the warehouse in any way.
- This engine does **NOT** approve, reject, or execute actions.
- Generated actions remain in status ``PROPOSED`` at all times.

Design principles:
- Deterministic classification over LLM-based guessing.
- Safety > Automation coverage.
- Structured parameters → validated identifiers → SQL generation.
- Never interpolate raw recommendation text into SQL.
- Never fabricate rollback for irreversible operations.
- Never auto-generate executable plans for destructive operations.

No LLM calls, no database writes, no HTTP, no execution.
"""

from __future__ import annotations

import hashlib
import re
import uuid
import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from app.models.warehouse import Warehouse
from app.context.shared_context import SharedContext

logger = logging.getLogger(__name__)


# ── Enumerations ─────────────────────────────────────────────────────


class AutomationStatus(str, Enum):
    """Classification of a recommendation's automation eligibility."""

    AUTOMATABLE = "AUTOMATABLE"
    NOT_AUTOMATABLE = "NOT_AUTOMATABLE"
    REQUIRES_MANUAL_REVIEW = "REQUIRES_MANUAL_REVIEW"
    INSUFFICIENT_INFORMATION = "INSUFFICIENT_INFORMATION"


class ActionStatus(str, Enum):
    """Lifecycle status of an action plan."""

    PROPOSED = "PROPOSED"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXECUTING = "EXECUTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    VERIFIED = "VERIFIED"


class RiskLevel(str, Enum):
    """Risk classification for an action."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class SafetyClass(str, Enum):
    """Safety classification for an action's impact on warehouse state."""

    READ_ONLY = "READ_ONLY"
    REVERSIBLE_WRITE = "REVERSIBLE_WRITE"
    IRREVERSIBLE_OR_HIGH_RISK = "IRREVERSIBLE_OR_HIGH_RISK"


class NonAutomatableReason(str, Enum):
    """Reasons why a recommendation cannot be automated."""

    UNSUPPORTED_ACTION = "UNSUPPORTED_ACTION"
    INSUFFICIENT_INFORMATION = "INSUFFICIENT_INFORMATION"
    HIGH_RISK = "HIGH_RISK"
    IRREVERSIBLE = "IRREVERSIBLE"
    MISSING_TARGET = "MISSING_TARGET"
    AMBIGUOUS_TARGET = "AMBIGUOUS_TARGET"
    MISSING_PRECONDITION = "MISSING_PRECONDITION"
    MANUAL_REVIEW_REQUIRED = "MANUAL_REVIEW_REQUIRED"
    SECURITY_SENSITIVE = "SECURITY_SENSITIVE"


# ── Safe identifier validation ───────────────────────────────────────

# PostgreSQL identifier: alphanumeric + underscores, starting with letter or _
_SAFE_IDENTIFIER_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]{0,62}$")


def _is_safe_identifier(value: str) -> bool:
    """Check whether a value is a safe PostgreSQL identifier."""
    return bool(_SAFE_IDENTIFIER_RE.match(value))


def _quote_identifier(value: str) -> str:
    """
    Safely quote a PostgreSQL identifier using double quotes.

    Raises ValueError if the identifier contains dangerous characters.
    """
    if not value or not _is_safe_identifier(value):
        raise ValueError(f"Unsafe or invalid identifier: {value!r}")
    # Double-quote escaping: replace any embedded " with ""
    escaped = value.replace('"', '""')
    return f'"{escaped}"'


# ── Action Registry ──────────────────────────────────────────────────


class _ActionDefinition:
    """Definition for a single supported action type."""

    def __init__(
        self,
        action_type: str,
        description: str,
        required_params: list[str],
        risk: RiskLevel,
        safety_class: SafetyClass,
        is_reversible: bool,
        is_destructive: bool,
    ) -> None:
        self.action_type = action_type
        self.description = description
        self.required_params = required_params
        self.risk = risk
        self.safety_class = safety_class
        self.is_reversible = is_reversible
        self.is_destructive = is_destructive


# Centralized registry of supported action types.
# Only actions that AetherArchive can describe with high confidence are included.
_ACTION_REGISTRY: dict[str, _ActionDefinition] = {
    "CREATE_INDEX": _ActionDefinition(
        action_type="CREATE_INDEX",
        description="Create a B-tree index on a specified column to improve query performance.",
        required_params=["schema", "table", "column"],
        risk=RiskLevel.MEDIUM,
        safety_class=SafetyClass.REVERSIBLE_WRITE,
        is_reversible=True,
        is_destructive=False,
    ),
    "ANALYZE_TABLE": _ActionDefinition(
        action_type="ANALYZE_TABLE",
        description="Run ANALYZE on a table to update PostgreSQL planner statistics.",
        required_params=["schema", "table"],
        risk=RiskLevel.LOW,
        safety_class=SafetyClass.REVERSIBLE_WRITE,
        is_reversible=True,
        is_destructive=False,
    ),
    "REVIEW_PERMISSION": _ActionDefinition(
        action_type="REVIEW_PERMISSION",
        description="Review and audit database permissions for a specific object.",
        required_params=["schema", "table"],
        risk=RiskLevel.LOW,
        safety_class=SafetyClass.READ_ONLY,
        is_reversible=True,
        is_destructive=False,
    ),
    "REVIEW_SECURITY_SETTING": _ActionDefinition(
        action_type="REVIEW_SECURITY_SETTING",
        description="Review security settings and identify areas of concern.",
        required_params=["schema", "table"],
        risk=RiskLevel.LOW,
        safety_class=SafetyClass.READ_ONLY,
        is_reversible=True,
        is_destructive=False,
    ),
}


# ── Recommendation → Action mapping ─────────────────────────────────

# Maps recommendation_type to its corresponding action type.
# Only recommendation types that can be safely and deterministically
# converted to structured actions are included here.
_RECOMMENDATION_TO_ACTION: dict[str, str] = {
    "large_table_indexing": "ANALYZE_TABLE",
}

# Recommendation types that are informational / advisory and should
# NOT produce executable actions.
_INFORMATIONAL_TYPES: frozenset[str] = frozenset({
    "weak_table_name",
    "weak_column_name",
    "empty_table",
    "wide_table",
    "missing_primary_key",
    "missing_uniqueness_constraints",
    "excessive_table_nullability",
    "invalid_or_unknown_datatype",
    "inconsistent_datatypes",
})

# Recommendation categories where all items require manual security review.
_SECURITY_SENSITIVE_CATEGORIES: frozenset[str] = frozenset({
    "Security",
})


# ── AutomationEngine ────────────────────────────────────────────────


class AutomationEngine:
    """
    Deterministic engine that transforms recommendations into structured
    action plans.

    The engine:
    1. Reads recommendations from SharedContext.
    2. Classifies each recommendation's automation eligibility.
    3. For automatable recommendations, generates a structured action plan
       with preconditions, safety checks, rollback plan, and verification plan.
    4. Never executes any SQL or modifies the warehouse.
    """

    def analyse(
        self,
        warehouse: Warehouse,
        context: SharedContext,
        progress_callback: Any = None,
    ) -> dict[str, Any]:
        """
        Analyse recommendations and produce structured action plans.

        Parameters
        ──────────
        warehouse : Warehouse
            A registered ``Warehouse`` ORM instance.
        context : SharedContext
            The shared context containing recommendation results.
        progress_callback : Any, optional
            Callback for progress reporting.

        Returns
        ───────
        dict[str, Any]
            Structured automation result with summary and action plans.
        """
        if progress_callback:
            progress_callback("Retrieving recommendations for automation analysis...", 5)

        recommendation_data = context.get_agent_result("recommendation") or {}
        recommendations = recommendation_data.get("recommendations", [])

        if progress_callback:
            progress_callback(
                f"Analysing {len(recommendations)} recommendation(s) for automation eligibility...",
                15,
            )

        action_plans: list[dict[str, Any]] = []
        non_automatable: list[dict[str, Any]] = []

        total = len(recommendations)
        for idx, rec in enumerate(recommendations):
            if progress_callback and total > 0:
                pct = 20 + int((idx / total) * 60)
                progress_callback(
                    f"Classifying recommendation: {rec.get('title', 'unknown')}...",
                    pct,
                )

            classification = self._classify_recommendation(rec)

            if classification["automation_status"] == AutomationStatus.AUTOMATABLE:
                plan = self._generate_action_plan(rec, classification)
                action_plans.append(plan)
            else:
                non_automatable.append(classification)

        if progress_callback:
            progress_callback("Generating automation summary...", 85)

        # Build summary
        automatable_count = len(action_plans)
        manual_review_count = sum(
            1 for n in non_automatable
            if n["automation_status"] in (
                AutomationStatus.REQUIRES_MANUAL_REVIEW,
                AutomationStatus.INSUFFICIENT_INFORMATION,
            )
        )
        not_automatable_count = sum(
            1 for n in non_automatable
            if n["automation_status"] == AutomationStatus.NOT_AUTOMATABLE
        )

        result = {
            "status": "COMPLETED",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "total_recommendations": total,
                "automatable": automatable_count,
                "manual_review": manual_review_count,
                "not_automatable": not_automatable_count,
            },
            "action_plans": action_plans,
            "non_automatable": non_automatable,
        }

        if progress_callback:
            progress_callback("Automation analysis completed.", 100)

        return result

    # ── Classification ───────────────────────────────────────────────

    def _classify_recommendation(self, rec: dict[str, Any]) -> dict[str, Any]:
        """
        Classify a single recommendation's automation eligibility.

        Returns a dict with automation_status, reason, and classification metadata.
        """
        rec_type = rec.get("recommendation_type", "")
        category = rec.get("category", "")
        schema = rec.get("schema", "")
        table = rec.get("table", "")

        # 1. Security-sensitive recommendations always require manual review
        if category in _SECURITY_SENSITIVE_CATEGORIES:
            return {
                "recommendation_type": rec_type,
                "title": rec.get("title", ""),
                "automation_status": AutomationStatus.REQUIRES_MANUAL_REVIEW,
                "reason": NonAutomatableReason.SECURITY_SENSITIVE,
                "reason_detail": (
                    "Security-related recommendations require manual review "
                    "before any automated action can be proposed."
                ),
            }

        # 2. Informational / advisory recommendations are not automatable
        if rec_type in _INFORMATIONAL_TYPES:
            return {
                "recommendation_type": rec_type,
                "title": rec.get("title", ""),
                "automation_status": AutomationStatus.NOT_AUTOMATABLE,
                "reason": NonAutomatableReason.UNSUPPORTED_ACTION,
                "reason_detail": (
                    "This recommendation is informational or advisory. "
                    "No automated action can be safely constructed."
                ),
            }

        # 3. Check if we have a known mapping
        action_type = _RECOMMENDATION_TO_ACTION.get(rec_type)
        if action_type is None:
            return {
                "recommendation_type": rec_type,
                "title": rec.get("title", ""),
                "automation_status": AutomationStatus.REQUIRES_MANUAL_REVIEW,
                "reason": NonAutomatableReason.UNSUPPORTED_ACTION,
                "reason_detail": (
                    f"Recommendation type '{rec_type}' does not have a supported "
                    "automation mapping. Manual review is required."
                ),
            }

        # 4. Validate target information
        action_def = _ACTION_REGISTRY.get(action_type)
        if action_def is None:
            return {
                "recommendation_type": rec_type,
                "title": rec.get("title", ""),
                "automation_status": AutomationStatus.REQUIRES_MANUAL_REVIEW,
                "reason": NonAutomatableReason.UNSUPPORTED_ACTION,
                "reason_detail": f"Action type '{action_type}' is not registered.",
            }

        # 5. Validate required parameters are present and safe
        missing_params = []
        for param in action_def.required_params:
            value = rec.get(param, "")
            if not value or (isinstance(value, str) and not value.strip()):
                missing_params.append(param)
            elif isinstance(value, str) and not _is_safe_identifier(value):
                return {
                    "recommendation_type": rec_type,
                    "title": rec.get("title", ""),
                    "automation_status": AutomationStatus.REQUIRES_MANUAL_REVIEW,
                    "reason": NonAutomatableReason.AMBIGUOUS_TARGET,
                    "reason_detail": (
                        f"Parameter '{param}' contains an unsafe identifier: {value!r}."
                    ),
                }

        if missing_params:
            return {
                "recommendation_type": rec_type,
                "title": rec.get("title", ""),
                "automation_status": AutomationStatus.INSUFFICIENT_INFORMATION,
                "reason": NonAutomatableReason.MISSING_TARGET,
                "reason_detail": (
                    f"Required parameter(s) missing: {', '.join(missing_params)}. "
                    "Cannot safely construct an executable action."
                ),
            }

        # All checks passed — automatable
        return {
            "recommendation_type": rec_type,
            "title": rec.get("title", ""),
            "automation_status": AutomationStatus.AUTOMATABLE,
            "action_type": action_type,
            "reason": None,
            "reason_detail": None,
        }

    # ── Action plan generation ───────────────────────────────────────

    def _generate_action_plan(
        self,
        rec: dict[str, Any],
        classification: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Generate a structured action plan for an automatable recommendation.

        The plan is a data structure — it never executes anything.
        """
        action_type = classification["action_type"]
        action_def = _ACTION_REGISTRY[action_type]

        schema = rec.get("schema", "")
        table = rec.get("table", "")
        column = rec.get("column")

        # Generate a stable action_id from recommendation identity
        rec_identity = f"{rec.get('recommendation_type', '')}:{schema}:{table}:{column or ''}"
        action_id = hashlib.sha256(rec_identity.encode("utf-8")).hexdigest()[:16]

        target = {
            "schema": schema,
            "table": table,
        }
        if column:
            target["column"] = column

        # Generate the statement, preconditions, safety checks, etc.
        statement = self._generate_statement(action_type, schema, table, column)
        preconditions = self._generate_preconditions(action_type, schema, table, column)
        safety_checks = self._generate_safety_checks(action_type, schema, table, column)
        rollback_plan = self._generate_rollback_plan(action_type, schema, table, column)
        verification_plan = self._generate_verification_plan(action_type, schema, table, column)

        # Collect evidence from the recommendation itself (no hallucination)
        evidence = []
        if rec.get("source_agents"):
            evidence.append(f"Source agents: {', '.join(rec['source_agents'])}")
        if rec.get("description"):
            evidence.append(f"Recommendation: {rec['description']}")

        return {
            "action_id": action_id,
            "recommendation_type": rec.get("recommendation_type", ""),
            "action_type": action_type,
            "status": ActionStatus.PROPOSED.value,
            "automation_status": AutomationStatus.AUTOMATABLE.value,
            "target": target,
            "description": action_def.description,
            "statement": statement,
            "parameters": {
                "schema": schema,
                "table": table,
                **({"column": column} if column else {}),
            },
            "risk_level": action_def.risk.value,
            "impact_level": rec.get("impact", "MEDIUM"),
            "safety_class": action_def.safety_class.value,
            "preconditions": preconditions,
            "safety_checks": safety_checks,
            "rollback_plan": rollback_plan,
            "verification_plan": verification_plan,
            "requires_approval": action_def.safety_class != SafetyClass.READ_ONLY,
            "requires_verification": True,
            "is_destructive": action_def.is_destructive,
            "is_reversible": action_def.is_reversible,
            "is_executable": True,
            "executed": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source_agent": "automation",
            "evidence": evidence,
        }

    # ── Statement generation ─────────────────────────────────────────
    # Statements are generated from validated structured parameters,
    # NOT from raw recommendation text. All identifiers are validated.

    def _generate_statement(
        self,
        action_type: str,
        schema: str,
        table: str,
        column: str | None,
    ) -> str | None:
        """
        Generate a safe SQL statement from validated structured parameters.

        Returns None if the action type does not produce SQL.
        """
        if action_type == "CREATE_INDEX":
            if not column:
                return None
            q_schema = _quote_identifier(schema)
            q_table = _quote_identifier(table)
            q_column = _quote_identifier(column)
            index_name = f"idx_{table}_{column}"
            if not _is_safe_identifier(index_name):
                # Fallback to a safe generated name
                index_name = f"idx_{hashlib.sha256(f'{table}_{column}'.encode()).hexdigest()[:12]}"
            q_index = _quote_identifier(index_name)
            return f"CREATE INDEX {q_index} ON {q_schema}.{q_table} ({q_column})"

        if action_type == "ANALYZE_TABLE":
            q_schema = _quote_identifier(schema)
            q_table = _quote_identifier(table)
            return f"ANALYZE {q_schema}.{q_table}"

        # READ_ONLY actions don't produce mutation statements
        if action_type in ("REVIEW_PERMISSION", "REVIEW_SECURITY_SETTING"):
            return None

        return None

    # ── Preconditions ────────────────────────────────────────────────

    def _generate_preconditions(
        self,
        action_type: str,
        schema: str,
        table: str,
        column: str | None,
    ) -> list[str]:
        """Generate preconditions that must hold before an action can execute."""
        preconditions = [
            f"Target schema '{schema}' must exist.",
            f"Target table '{schema}.{table}' must exist.",
            "Action must be approved before execution.",
        ]

        if action_type == "CREATE_INDEX" and column:
            preconditions.append(f"Target column '{column}' must exist in '{schema}.{table}'.")
            index_name = f"idx_{table}_{column}"
            preconditions.append(f"Index name '{index_name}' must not conflict with an existing index.")

        if action_type in ("REVIEW_PERMISSION", "REVIEW_SECURITY_SETTING"):
            preconditions.append("Database access must be available for inspection.")

        return preconditions

    # ── Safety checks ────────────────────────────────────────────────

    def _generate_safety_checks(
        self,
        action_type: str,
        schema: str,
        table: str,
        column: str | None,
    ) -> list[str]:
        """Generate safety checks that should be verified before execution."""
        checks = [
            f"Target table '{schema}.{table}' must exist.",
            "Requested operation must not be destructive.",
            "Action must be approved before execution.",
        ]

        if action_type == "CREATE_INDEX" and column:
            checks.append(f"Target column '{column}' must exist in '{schema}.{table}'.")
            checks.append("Index name must not conflict with existing indexes.")

        if action_type == "ANALYZE_TABLE":
            checks.append("Table must be accessible for statistics collection.")

        return checks

    # ── Rollback plan ────────────────────────────────────────────────

    def _generate_rollback_plan(
        self,
        action_type: str,
        schema: str,
        table: str,
        column: str | None,
    ) -> dict[str, Any]:
        """
        Generate a rollback plan if the action is reversible.

        Returns a dict describing the rollback. Never fabricates rollback
        for irreversible operations.
        """
        if action_type == "CREATE_INDEX" and column:
            index_name = f"idx_{table}_{column}"
            if not _is_safe_identifier(index_name):
                index_name = f"idx_{hashlib.sha256(f'{table}_{column}'.encode()).hexdigest()[:12]}"
            try:
                q_schema = _quote_identifier(schema)
                q_index = _quote_identifier(index_name)
                rollback_stmt = f"DROP INDEX {q_schema}.{q_index}"
            except ValueError:
                return {
                    "rollback_available": False,
                    "reason": "Cannot generate safe rollback statement.",
                }
            return {
                "rollback_available": True,
                "statement": rollback_stmt,
                "description": f"Drop the created index '{index_name}'.",
            }

        if action_type == "ANALYZE_TABLE":
            return {
                "rollback_available": True,
                "statement": None,
                "description": "ANALYZE is a statistics update; previous statistics are replaced. No explicit rollback needed.",
            }

        if action_type in ("REVIEW_PERMISSION", "REVIEW_SECURITY_SETTING"):
            return {
                "rollback_available": True,
                "statement": None,
                "description": "Read-only action; no rollback necessary.",
            }

        return {
            "rollback_available": False,
            "reason": "Rollback is not defined for this action type.",
        }

    # ── Verification plan ────────────────────────────────────────────

    def _generate_verification_plan(
        self,
        action_type: str,
        schema: str,
        table: str,
        column: str | None,
    ) -> dict[str, Any]:
        """Generate a verification plan describing how to confirm action success."""
        if action_type == "CREATE_INDEX" and column:
            index_name = f"idx_{table}_{column}"
            return {
                "verification_type": "INDEX_EXISTS",
                "description": f"Verify index '{index_name}' exists on '{schema}.{table}'.",
                "check_query": (
                    f"SELECT 1 FROM pg_indexes "
                    f"WHERE schemaname = '{schema}' AND tablename = '{table}' "
                    f"AND indexname = '{index_name}'"
                ),
            }

        if action_type == "ANALYZE_TABLE":
            return {
                "verification_type": "STATISTICS_UPDATED",
                "description": f"Verify statistics have been updated for '{schema}.{table}'.",
                "check_query": (
                    f"SELECT last_analyze FROM pg_stat_user_tables "
                    f"WHERE schemaname = '{schema}' AND relname = '{table}'"
                ),
            }

        if action_type in ("REVIEW_PERMISSION", "REVIEW_SECURITY_SETTING"):
            return {
                "verification_type": "MANUAL_VERIFICATION",
                "description": "Manual review completion should be confirmed by the user.",
                "check_query": None,
            }

        return {
            "verification_type": "MANUAL_VERIFICATION",
            "description": "Verification is not defined for this action type.",
            "check_query": None,
        }
