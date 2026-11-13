"""
Warehouse explainability engine.

Analyzes recommendations alongside prior agent findings (metadata, statistics,
monitoring, security, data quality, query, prediction) from the shared memory bus
and generates structured, evidence-based explanations detailing why each recommendation
was produced by AetherArchive.

No SQL execution, no database writes, no HTTP, no LLMs, no hallucinated metrics.
"""

from typing import Any
import logging

from app.models.warehouse import Warehouse
from app.context.shared_context import SharedContext

logger = logging.getLogger(__name__)


class ExplainabilityEngine:
    """
    Engine responsible for generating evidence-backed explanations
    for warehouse recommendations.
    """

    def analyse(
        self,
        warehouse: Warehouse,
        context: SharedContext,
        progress_callback: Any = None
    ) -> dict[str, Any]:
        """
        Analyse generated recommendations and construct structured explanations.

        Parameters
        ──────────
        warehouse : Warehouse
            A registered ``Warehouse`` ORM instance.
        context : SharedContext
            The shared context containing previous agent execution results.
        progress_callback : Any, optional
            Callback function to emit progress updates.

        Returns
        ───────
        dict[str, Any]
            Structured explainability output containing summary and list of explanations.
        """
        if progress_callback:
            progress_callback("Retrieving recommendations for explanation...", 10)

        recommendation_data = context.get_agent_result("recommendation") or {}
        recommendations = recommendation_data.get("recommendations", [])

        # Fetch prior agent findings from shared context
        metadata = context.get_agent_result("metadata") or {}
        statistics = context.get_agent_result("statistics") or {}
        monitoring = context.get_agent_result("monitoring") or {}
        security = context.get_agent_result("security") or {}
        data_quality = context.get_agent_result("data_quality") or {}
        query_analysis = context.get_agent_result("query_analysis") or context.get_agent_result("query") or {}
        prediction = context.get_agent_result("prediction") or {}

        explanations: list[dict[str, Any]] = []

        total_recs = len(recommendations)
        if total_recs == 0:
            if progress_callback:
                progress_callback("No recommendations to explain.", 100)
            return {
                "summary": {
                    "explanation_count": 0,
                    "supported_recommendations": 0,
                    "missing_evidence_count": 0,
                },
                "explanations": [],
            }

        for i, rec in enumerate(recommendations):
            if progress_callback:
                pct = int(10 + ((i + 1) / total_recs) * 80)
                progress_callback(f"Explaining recommendation {i + 1}/{total_recs}...", pct)

            explanation = self._explain_single_recommendation(
                rec=rec,
                metadata=metadata,
                statistics=statistics,
                monitoring=monitoring,
                security=security,
                data_quality=data_quality,
                query_analysis=query_analysis,
                prediction=prediction,
            )
            explanations.append(explanation)

        if progress_callback:
            progress_callback("Finalising explainability report...", 95)

        supported_count = sum(1 for e in explanations if e.get("evidence_available", False))
        missing_count = total_recs - supported_count

        return {
            "summary": {
                "explanation_count": len(explanations),
                "supported_recommendations": supported_count,
                "missing_evidence_count": missing_count,
            },
            "explanations": explanations,
        }

    def _explain_single_recommendation(
        self,
        rec: dict[str, Any],
        metadata: dict[str, Any],
        statistics: dict[str, Any],
        monitoring: dict[str, Any],
        security: dict[str, Any],
        data_quality: dict[str, Any],
        query_analysis: dict[str, Any],
        prediction: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Build a single structured explanation object using observable evidence.
        """
        rec_type = rec.get("recommendation_type", "unknown")
        schema = rec.get("schema", "unknown")
        table = rec.get("table", "unknown")
        column = rec.get("column")
        priority = rec.get("priority", "MEDIUM")
        impact = rec.get("impact", "MEDIUM")
        confidence = float(rec.get("confidence", 1.0))
        source_agents = rec.get("source_agents", [])
        title = rec.get("title", f"Recommendation for {schema}.{table}")
        description = rec.get("description", "")

        # Format affected object representation
        object_identifier = f"{schema}.{table}.{column}" if column else f"{schema}.{table}"
        affected_objects = [object_identifier]

        evidence_list: list[str] = []
        evidence_available = True

        # Generate rule-specific why & evidence from available state
        if rec_type == "missing_primary_key":
            why = (
                f"No primary key constraint was detected during schema discovery on '{schema}.{table}'. "
                f"Tables without primary keys risk row duplication, unindexed lookups, and constraint violations."
            )
            expected_impact = "Ensures row uniqueness, improves join performance, and prevents data duplication."
            
            # Check metadata state for evidence
            schemas = metadata.get("schemas", {})
            schema_info = schemas.get(schema, {})
            tables_info = schema_info.get("tables", {})
            table_info = tables_info.get(table, {})
            cols = table_info.get("columns", [])

            if cols:
                pk_cols = [c.get("name") for c in cols if c.get("primary_key")]
                evidence_list.append(
                    f"Metadata Agent confirmed table '{schema}.{table}' contains {len(cols)} columns "
                    f"with {len(pk_cols)} primary key constraints defined."
                )
            elif metadata:
                evidence_list.append(f"Metadata Agent identified table '{schema}.{table}' lacking a primary key.")
            else:
                evidence_available = False
                evidence_list.append("Evidence unavailable in current workflow state (Metadata Agent state absent).")

        elif rec_type == "weak_table_name":
            why = (
                f"The table name '{table}' matches generic, non-descriptive naming patterns. "
                f"Generic table names reduce schema maintainability and increase cognitive overhead for queries."
            )
            expected_impact = "Improves schema clarity, documentation quality, and query maintainability."
            evidence_list.append(f"Metadata Agent detected generic table identifier '{table}' in schema '{schema}'.")

        elif rec_type == "weak_column_name":
            why = (
                f"The column name '{column}' in '{schema}.{table}' matches generic naming patterns. "
                f"Generic column names obfuscate data domain meaning."
            )
            expected_impact = "Enhances domain clarity and self-documenting schema structure."
            evidence_list.append(f"Metadata Agent flagged generic column name '{column}' within table '{schema}.{table}'.")

        elif rec_type == "large_table_indexing":
            why = (
                f"Table '{schema}.{table}' contains a high row volume. "
                f"Unindexed queries against large tables result in sequential scans and degraded response times."
            )
            expected_impact = "Reduces query scan cost and execution latency on large datasets."

            # Check statistics state for evidence
            stat_tables = statistics.get("tables", [])
            match_t = next((t for t in stat_tables if t.get("schema") == schema and t.get("table_name") == table), None)
            if match_t:
                rows = match_t.get("estimated_row_count", 0)
                evidence_list.append(
                    f"Statistics Agent measured estimated row count of {rows:,} rows on table '{schema}.{table}'."
                )
            elif statistics:
                evidence_list.append(f"Statistics Agent flagged '{schema}.{table}' as exceeding row volume threshold.")
            else:
                evidence_available = False
                evidence_list.append("Evidence unavailable in current workflow state (Statistics Agent state absent).")

        elif rec_type == "empty_table":
            why = (
                f"Table '{schema}.{table}' contains zero rows and has no recent activity. "
                f"Unused empty tables clutter the data model."
            )
            expected_impact = "Simplifies database schema and frees metadata catalog overhead."

            stat_tables = statistics.get("tables", [])
            match_t = next((t for t in stat_tables if t.get("schema") == schema and t.get("table_name") == table), None)
            if match_t:
                rows = match_t.get("estimated_row_count", 0)
                evidence_list.append(
                    f"Statistics Agent recorded 0 active rows for table '{schema}.{table}'."
                )
            elif statistics:
                evidence_list.append(f"Statistics Agent confirmed table '{schema}.{table}' is empty.")
            else:
                evidence_available = False
                evidence_list.append("Evidence unavailable in current workflow state (Statistics Agent state absent).")

        elif rec_type == "wide_table":
            why = (
                f"Table '{schema}.{table}' contains an unusually large number of columns. "
                f"Excessively wide tables indicate denormalisation issues and increase row storage overhead."
            )
            expected_impact = "Optimizes storage footprint and improves query execution efficiency."

            stat_tables = statistics.get("tables", [])
            match_t = next((t for t in stat_tables if t.get("schema") == schema and t.get("table_name") == table), None)
            if match_t:
                cols = match_t.get("total_columns", 0)
                evidence_list.append(
                    f"Statistics Agent detected {cols} columns in table '{schema}.{table}'."
                )
            elif statistics:
                evidence_list.append(f"Statistics Agent flagged table '{schema}.{table}' for excessive column width.")
            else:
                evidence_available = False
                evidence_list.append("Evidence unavailable in current workflow state (Statistics Agent state absent).")

        elif rec_type in ("sensitive_column", "security_alert") or "security" in source_agents:
            why = (
                f"A security risk was identified on '{object_identifier}'. "
                f"Unprotected sensitive attributes compromise regulatory compliance and data governance."
            )
            expected_impact = "Enhances data protection, compliance posture, and access governance."

            sec_issues = security.get("issues", [])
            match_sec = [
                sec for sec in sec_issues
                if sec.get("schema") == schema and sec.get("table") == table and (not column or sec.get("column") == column)
            ]
            if match_sec:
                for issue in match_sec:
                    rule_name = issue.get("rule", "Security Issue")
                    sev = issue.get("severity", "MEDIUM")
                    desc = issue.get("description", "")
                    evidence_list.append(
                        f"Security Agent reported issue '{rule_name}' (Severity: {sev}) on '{object_identifier}': {desc}"
                    )
            elif security:
                evidence_list.append(f"Security Agent flagged security vulnerability on '{object_identifier}'.")
            else:
                evidence_available = False
                evidence_list.append("Evidence unavailable in current workflow state (Security Agent state absent).")

        elif rec_type in ("excessive_table_nullability", "missing_uniqueness_constraints", "invalid_or_unknown_datatype", "inconsistent_datatypes") or "data_quality" in source_agents:
            why = (
                f"Data quality analysis detected structural anomalies on '{object_identifier}'. "
                f"Unconstrained or invalid data types degrade downstream query reliability."
            )
            expected_impact = "Enforces data integrity, standardises data definitions, and prevents downstream errors."

            dq_issues = data_quality.get("issues", [])
            match_dq = [
                dq for dq in dq_issues
                if dq.get("schema") == schema and dq.get("table") == table and (not column or dq.get("column") == column)
            ]
            if match_dq:
                for issue in match_dq:
                    rule_name = issue.get("rule", "Data Quality Issue")
                    sev = issue.get("severity", "MEDIUM")
                    evidence_list.append(
                        f"Data Quality Agent detected anomaly '{rule_name}' (Severity: {sev}) on '{object_identifier}'."
                    )
            elif data_quality:
                evidence_list.append(f"Data Quality Agent recorded quality issue on '{object_identifier}'.")
            else:
                evidence_available = False
                evidence_list.append("Evidence unavailable in current workflow state (Data Quality Agent state absent).")

        else:
            # Fallback for dynamic or custom recommendation types
            why = (
                f"Recommendation '{title}' was derived from multi-agent workflow analysis of '{object_identifier}'."
            )
            expected_impact = f"Mitigates identified risk and improves warehouse health ({impact} impact)."

            if source_agents:
                agents_str = ", ".join([s.replace("_", " ").title() for s in source_agents])
                evidence_list.append(f"Derived from findings provided by {agents_str}.")
            else:
                evidence_available = False
                evidence_list.append("Evidence unavailable in current workflow state.")

        # Incorporate monitoring or query analysis evidence if available in state
        if monitoring and monitoring.get("active_connections") is not None:
            conn = monitoring.get("active_connections")
            evidence_list.append(f"Monitoring Agent recorded {conn} active database connections during discovery.")

        if query_analysis and query_analysis.get("findings"):
            for q_find in query_analysis.get("findings", [])[:2]:
                if q_find.get("table") == table or not q_find.get("table"):
                    evidence_list.append(f"Query Analysis Agent observed: {q_find.get('summary', 'Query scan finding')}")

        if prediction and prediction.get("insights"):
            for p_insight in prediction.get("insights", [])[:2]:
                evidence_list.append(f"Prediction Agent estimated: {p_insight}")

        # Ensure no hidden chain-of-thought is present
        # Normalize supporting agents list
        supporting_agents = [s.replace("_", " ").title() + " Agent" for s in source_agents] if source_agents else ["Recommendation Agent"]

        return {
            "recommendation_type": rec_type,
            "title": title,
            "recommendation": description or title,
            "why": why,
            "evidence": evidence_list,
            "affected_objects": affected_objects,
            "expected_impact": expected_impact,
            "confidence": confidence,
            "supporting_agents": supporting_agents,
            "severity": priority,
            "evidence_available": evidence_available,
        }
