"""
Current Condition Evaluator (R3).

Evaluates whether the underlying condition associated with a recommendation candidate
currently exists in the target database warehouse.

CRITICAL SCOPE RESTRICTIONS (R3):
- Strictly OBSERVATIONAL and evidence-gathering.
- READ-ONLY catalog and statistics queries against the target warehouse.
- Bounded query timeout (statement_timeout = 30s).
- Re-validates target identifiers (schema, table, column) via safe identifier checks.
- Zero raw user data extraction (inspects PostgreSQL system catalogs only).
- Never returns database passwords, connection URLs, or secret credentials.
- Does NOT alter Recommendation Agent decision logic.
- Does NOT suppress, block, or automatically reject recommendations.
"""

from datetime import datetime, timezone
import logging
import time
from typing import Any, Dict, List, Optional
from sqlalchemy import text

from app.models.warehouse import Warehouse
from app.warehouse.connector import WarehouseConnector
from app.warehouse.automation import _is_safe_identifier

logger = logging.getLogger(__name__)

STATEMENT_TIMEOUT_MS = 30000


class ConditionStatus:
    PRESENT = "PRESENT"
    RESOLVED = "RESOLVED"
    UNCERTAIN = "UNCERTAIN"
    NOT_MEASURABLE = "NOT_MEASURABLE"


class CurrentConditionEvaluator:
    """
    Evaluator layer responsible for querying system catalogs to determine
    whether a recommendation candidate's condition currently exists in the warehouse.
    """

    @classmethod
    def evaluate_current_condition(
        cls,
        warehouse: Warehouse,
        candidate: Dict[str, Any],
        historical_match: Optional[Dict[str, Any]] = None,
        fingerprint: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Evaluate the current warehouse condition for a recommendation candidate.

        Parameters
        ----------
        warehouse : Warehouse
            The target warehouse ORM instance.
        candidate : Dict[str, Any]
            The recommendation candidate payload.
        historical_match : Optional[Dict[str, Any]]
            Optional R1/R2 historical outcome match summary for context.
        fingerprint : Optional[str]
            Optional R2 SHA-256 fingerprint string.

        Returns
        -------
        Dict[str, Any]
            Structured current-state evaluation result.
        """
        rec_id = candidate.get("recommendation_id") or candidate.get("id") or "rec_unknown"
        action_type = (
            candidate.get("action_type")
            or candidate.get("recommendation_type")
            or candidate.get("type")
            or candidate.get("category")
            or "UNKNOWN"
        ).strip().upper()

        target = candidate.get("target") if isinstance(candidate.get("target"), dict) else {}
        params = candidate.get("parameters") if isinstance(candidate.get("parameters"), dict) else {}

        schema = (
            candidate.get("schema")
            or target.get("schema")
            or params.get("schema")
            or "public"
        )
        table = (
            candidate.get("table")
            or target.get("table")
            or params.get("table")
            or ""
        )
        column = (
            candidate.get("column")
            or target.get("column")
            or target.get("columns")
            or params.get("column")
            or params.get("columns")
        )

        norm_target = {
            "schema": str(schema).strip().lower(),
            "table": str(table).strip().lower(),
        }
        if column:
            norm_target["column"] = column

        # Only PostgreSQL is currently implemented for catalog evaluation
        if warehouse.db_type.lower() != "postgresql":
            return cls._build_result(
                recommendation_id=str(rec_id),
                fingerprint=fingerprint,
                warehouse_id=warehouse.id,
                action_type=action_type,
                target=norm_target,
                condition_status=ConditionStatus.NOT_MEASURABLE,
                condition_type="UNSUPPORTED_PROVIDER",
                evidence=[],
                measurement_available=False,
                reason=f"Current condition evaluator is not yet implemented for database type '{warehouse.db_type}'.",
                historical_match=historical_match,
            )

        # Dispatch action-type evaluator
        if action_type == "ANALYZE_TABLE":
            return cls._evaluate_analyze_table(
                warehouse=warehouse,
                schema=norm_target["schema"],
                table=norm_target["table"],
                recommendation_id=str(rec_id),
                fingerprint=fingerprint,
                target=norm_target,
                historical_match=historical_match,
            )
        elif action_type == "CREATE_INDEX":
            return cls._evaluate_create_index(
                warehouse=warehouse,
                schema=norm_target["schema"],
                table=norm_target["table"],
                column=norm_target.get("column"),
                recommendation_id=str(rec_id),
                fingerprint=fingerprint,
                target=norm_target,
                historical_match=historical_match,
            )
        else:
            return cls._evaluate_unsupported(
                warehouse=warehouse,
                action_type=action_type,
                recommendation_id=str(rec_id),
                fingerprint=fingerprint,
                target=norm_target,
                historical_match=historical_match,
            )

    @classmethod
    def _evaluate_analyze_table(
        cls,
        warehouse: Warehouse,
        schema: str,
        table: str,
        recommendation_id: str,
        fingerprint: Optional[str],
        target: Dict[str, Any],
        historical_match: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Evaluate current condition for ANALYZE_TABLE action by inspecting pg_stat_user_tables catalog.
        """
        if not schema or not table or not _is_safe_identifier(schema) or not _is_safe_identifier(table):
            return cls._build_result(
                recommendation_id=recommendation_id,
                fingerprint=fingerprint,
                warehouse_id=warehouse.id,
                action_type="ANALYZE_TABLE",
                target=target,
                condition_status=ConditionStatus.UNCERTAIN,
                condition_type="MODIFICATIONS_SINCE_ANALYZE",
                evidence=[],
                measurement_available=False,
                reason=f"Invalid or unsafe target identifiers: schema={schema!r}, table={table!r}.",
                historical_match=historical_match,
            )

        read_only_query = (
            "SELECT schemaname, relname, last_analyze, last_autoanalyze, "
            "n_mod_since_analyze, n_live_tup, n_dead_tup "
            "FROM pg_stat_user_tables "
            "WHERE schemaname = :schema AND relname = :table"
        )

        try:
            engine = WarehouseConnector.connect(warehouse)
            with engine.connect().execution_options(autocommit=True) as connection:
                try:
                    connection.execute(text(f"SET statement_timeout = {STATEMENT_TIMEOUT_MS}"))
                except Exception as timeout_err:
                    logger.warning(f"Could not set statement_timeout: {timeout_err}")

                result = connection.execute(
                    text(read_only_query),
                    {"schema": schema, "table": table},
                ).mappings().first()

            engine.dispose()

            if not result:
                # Table not found in user stats catalog
                evidence = [
                    {
                        "source": "pg_stat_user_tables",
                        "field": "table_existence",
                        "value": None,
                        "interpretation": f"Table '{schema}.{table}' was not found in pg_stat_user_tables system view.",
                    }
                ]
                return cls._build_result(
                    recommendation_id=recommendation_id,
                    fingerprint=fingerprint,
                    warehouse_id=warehouse.id,
                    action_type="ANALYZE_TABLE",
                    target=target,
                    condition_status=ConditionStatus.UNCERTAIN,
                    condition_type="MODIFICATIONS_SINCE_ANALYZE",
                    evidence=evidence,
                    measurement_available=True,
                    reason=f"Table '{schema}.{table}' is not present in PostgreSQL user statistics catalog.",
                    historical_match=historical_match,
                )

            last_analyze = result.get("last_analyze")
            last_autoanalyze = result.get("last_autoanalyze")
            n_mod = result.get("n_mod_since_analyze")
            n_live = result.get("n_live_tup")
            n_dead = result.get("n_dead_tup")

            last_analyze_str = last_analyze.isoformat() if last_analyze else None
            last_autoanalyze_str = last_autoanalyze.isoformat() if last_autoanalyze else None

            if n_mod is not None and n_mod > 0:
                n_mod_interp = f"{n_mod} modifications have occurred since the last recorded analyze."
            elif n_mod == 0:
                n_mod_interp = "No modifications are currently recorded since the latest analyze."
            else:
                n_mod_interp = f"Modifications since last analyze: {n_mod}"

            evidence = [
                {
                    "source": "pg_stat_user_tables",
                    "field": "last_analyze",
                    "value": last_analyze_str,
                    "interpretation": f"Manual analyze timestamp: {last_analyze_str or 'None'}",
                },
                {
                    "source": "pg_stat_user_tables",
                    "field": "last_autoanalyze",
                    "value": last_autoanalyze_str,
                    "interpretation": f"Autoanalyze timestamp: {last_autoanalyze_str or 'None'}",
                },
                {
                    "source": "pg_stat_user_tables",
                    "field": "n_mod_since_analyze",
                    "value": n_mod,
                    "interpretation": n_mod_interp,
                },
                {
                    "source": "pg_stat_user_tables",
                    "field": "n_live_tup",
                    "value": n_live,
                    "interpretation": f"Live tuple count: {n_live}",
                },
                {
                    "source": "pg_stat_user_tables",
                    "field": "n_dead_tup",
                    "value": n_dead,
                    "interpretation": f"Dead tuple count: {n_dead}",
                },
            ]

            # Current condition logic for ANALYZE_TABLE (observational current state semantics)
            if n_mod is not None and n_mod > 0:
                condition_status = ConditionStatus.PRESENT
                reason = f"{n_mod} modifications have occurred on table '{schema}.{table}' since the last recorded analyze."
            elif n_mod == 0 and (last_analyze is not None or last_autoanalyze is not None):
                condition_status = ConditionStatus.RESOLVED
                recent_ts = last_analyze_str or last_autoanalyze_str
                reason = f"No modifications are currently recorded on table '{schema}.{table}' since the latest analyze ({recent_ts})."
            elif n_mod == 0 and n_live == 0 and n_dead == 0:
                condition_status = ConditionStatus.RESOLVED
                reason = f"Table '{schema}.{table}' is empty with 0 modifications recorded since the latest analyze."
            else:
                condition_status = ConditionStatus.UNCERTAIN
                reason = f"Table '{schema}.{table}' catalog statistics are ambiguous or incomplete."

            return cls._build_result(
                recommendation_id=recommendation_id,
                fingerprint=fingerprint,
                warehouse_id=warehouse.id,
                action_type="ANALYZE_TABLE",
                target=target,
                condition_status=condition_status,
                condition_type="MODIFICATIONS_SINCE_ANALYZE",
                evidence=evidence,
                measurement_available=True,
                reason=reason,
                historical_match=historical_match,
            )

        except Exception as exc:
            safe_err = str(exc)
            if warehouse.username and warehouse.username in safe_err:
                safe_err = safe_err.replace(warehouse.username, "***")

            logger.error(f"Catalog query failed during ANALYZE condition check for warehouse {warehouse.id}: {safe_err}")
            return cls._build_result(
                recommendation_id=recommendation_id,
                fingerprint=fingerprint,
                warehouse_id=warehouse.id,
                action_type="ANALYZE_TABLE",
                target=target,
                condition_status=ConditionStatus.UNCERTAIN,
                condition_type="STALE_STATISTICS",
                evidence=[],
                measurement_available=False,
                reason=f"Failed to query PostgreSQL system catalogs: {safe_err}",
                historical_match=historical_match,
            )

    @classmethod
    def _evaluate_create_index(
        cls,
        warehouse: Warehouse,
        schema: str,
        table: str,
        column: Optional[Any],
        recommendation_id: str,
        fingerprint: Optional[str],
        target: Dict[str, Any],
        historical_match: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Evaluate current condition for CREATE_INDEX action by checking pg_indexes catalog.
        """
        col_str = ""
        if isinstance(column, list):
            col_str = "_".join(str(c).strip().lower() for c in column if c)
        elif isinstance(column, str):
            col_str = column.strip().lower()

        if not schema or not table or not _is_safe_identifier(schema) or not _is_safe_identifier(table):
            return cls._build_result(
                recommendation_id=recommendation_id,
                fingerprint=fingerprint,
                warehouse_id=warehouse.id,
                action_type="CREATE_INDEX",
                target=target,
                condition_status=ConditionStatus.UNCERTAIN,
                condition_type="MISSING_INDEX",
                evidence=[],
                measurement_available=False,
                reason=f"Invalid target identifiers: schema={schema!r}, table={table!r}.",
                historical_match=historical_match,
            )

        read_only_query = (
            "SELECT indexname, indexdef FROM pg_indexes "
            "WHERE schemaname = :schema AND tablename = :table"
        )

        try:
            engine = WarehouseConnector.connect(warehouse)
            with engine.connect().execution_options(autocommit=True) as connection:
                try:
                    connection.execute(text(f"SET statement_timeout = {STATEMENT_TIMEOUT_MS}"))
                except Exception as timeout_err:
                    logger.warning(f"Could not set statement_timeout: {timeout_err}")

                results = connection.execute(
                    text(read_only_query),
                    {"schema": schema, "table": table},
                ).mappings().all()

            engine.dispose()

            matching_index = None
            if col_str:
                for row in results:
                    def_str = (row.get("indexdef") or "").lower()
                    name_str = (row.get("indexname") or "").lower()
                    if col_str in def_str or col_str in name_str:
                        matching_index = row
                        break

            if matching_index:
                idx_name = matching_index.get("indexname")
                idx_def = matching_index.get("indexdef")
                evidence = [
                    {
                        "source": "pg_indexes",
                        "field": "indexname",
                        "value": idx_name,
                        "interpretation": f"Index '{idx_name}' exists on table '{schema}.{table}'.",
                    },
                    {
                        "source": "pg_indexes",
                        "field": "indexdef",
                        "value": idx_def,
                        "interpretation": f"Index definition: {idx_def}",
                    },
                ]
                return cls._build_result(
                    recommendation_id=recommendation_id,
                    fingerprint=fingerprint,
                    warehouse_id=warehouse.id,
                    action_type="CREATE_INDEX",
                    target=target,
                    condition_status=ConditionStatus.RESOLVED,
                    condition_type="MISSING_INDEX",
                    evidence=evidence,
                    measurement_available=True,
                    reason=f"Proposed index condition resolved: index '{idx_name}' already exists on '{schema}.{table}'.",
                    historical_match=historical_match,
                )
            else:
                evidence = [
                    {
                        "source": "pg_indexes",
                        "field": "index_count",
                        "value": len(results),
                        "interpretation": f"Table '{schema}.{table}' has {len(results)} index(es), none matching target '{col_str}'.",
                    }
                ]
                return cls._build_result(
                    recommendation_id=recommendation_id,
                    fingerprint=fingerprint,
                    warehouse_id=warehouse.id,
                    action_type="CREATE_INDEX",
                    target=target,
                    condition_status=ConditionStatus.PRESENT,
                    condition_type="MISSING_INDEX",
                    evidence=evidence,
                    measurement_available=True,
                    reason=f"Index on '{schema}.{table}' targeting '{col_str}' does not exist in catalog.",
                    historical_match=historical_match,
                )

        except Exception as exc:
            safe_err = str(exc)
            if warehouse.username and warehouse.username in safe_err:
                safe_err = safe_err.replace(warehouse.username, "***")

            logger.error(f"Catalog query failed during CREATE_INDEX condition check for warehouse {warehouse.id}: {safe_err}")
            return cls._build_result(
                recommendation_id=recommendation_id,
                fingerprint=fingerprint,
                warehouse_id=warehouse.id,
                action_type="CREATE_INDEX",
                target=target,
                condition_status=ConditionStatus.UNCERTAIN,
                condition_type="MISSING_INDEX",
                evidence=[],
                measurement_available=False,
                reason=f"Failed to query PostgreSQL index catalog: {safe_err}",
                historical_match=historical_match,
            )

    @classmethod
    def _evaluate_unsupported(
        cls,
        warehouse: Warehouse,
        action_type: str,
        recommendation_id: str,
        fingerprint: Optional[str],
        target: Dict[str, Any],
        historical_match: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Return structured NOT_MEASURABLE result for unsupported recommendation types."""
        return cls._build_result(
            recommendation_id=recommendation_id,
            fingerprint=fingerprint,
            warehouse_id=warehouse.id,
            action_type=action_type,
            target=target,
            condition_status=ConditionStatus.NOT_MEASURABLE,
            condition_type="UNSUPPORTED_ACTION_TYPE",
            evidence=[],
            measurement_available=False,
            reason=f"No authoritative PostgreSQL condition evaluator exists for recommendation type '{action_type}'.",
            historical_match=historical_match,
        )

    @classmethod
    def _build_result(
        cls,
        recommendation_id: str,
        fingerprint: Optional[str],
        warehouse_id: int,
        action_type: str,
        target: Dict[str, Any],
        condition_status: str,
        condition_type: str,
        evidence: List[Dict[str, Any]],
        measurement_available: bool,
        reason: str,
        historical_match: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Construct the canonical R3 current-state evaluation result dictionary."""
        return {
            "recommendation_id": recommendation_id,
            "fingerprint": fingerprint,
            "warehouse_id": warehouse_id,
            "action_type": action_type,
            "target": target,
            "condition_status": condition_status,
            "condition_type": condition_type,
            "evidence": evidence,
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
            "measurement_available": measurement_available,
            "reason": reason,
            "historical_match": historical_match,
        }
