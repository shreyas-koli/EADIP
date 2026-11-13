"""
Warehouse reporting engine.

Consolidates multi-agent warehouse intelligence findings (metadata, statistics,
monitoring, query analysis, security, data quality, predictions, recommendations,
and explainability) into a unified, structured, machine-readable overall report.

Read-only reporting engine:
- No database writes, no SQL execution, no recommendation execution.
- Distinguishes observed findings vs predictions vs recommendations.
- No hallucinated metrics or fabricated findings.
"""

from typing import Any, Dict, List
from datetime import datetime, timezone
import logging

from app.models.warehouse import Warehouse
from app.context.shared_context import SharedContext, AgentStatus

logger = logging.getLogger(__name__)


class ReportingEngine:
    """
    Consolidates warehouse findings into a comprehensive structured report.
    """

    def generate_report(
        self,
        warehouse: Warehouse,
        context: SharedContext,
        progress_callback: Any = None
    ) -> Dict[str, Any]:
        """
        Consolidate findings from SharedContext into a structured report.

        Parameters
        ──────────
        warehouse : Warehouse
            Target warehouse ORM instance.
        context : SharedContext
            Shared context storing prior agent execution results.
        progress_callback : Any, optional
            Callback for progress reporting.

        Returns
        ───────
        Dict[str, Any]
            The structured reporting result.
        """
        if progress_callback:
            progress_callback("Gathering agent findings for report...", 10)

        # Retrieve warehouse details
        wh_info = context.get_current_warehouse() or {
            "id": getattr(warehouse, "id", None),
            "name": getattr(warehouse, "name", "Unknown Warehouse"),
            "db_type": getattr(warehouse, "db_type", "unknown"),
        }

        # Gather agent results
        metadata = context.get_agent_result("metadata")
        statistics = context.get_agent_result("statistics")
        monitoring = context.get_agent_result("monitoring")
        query_analysis = context.get_agent_result("query_analysis") or context.get_agent_result("query")
        security = context.get_agent_result("security")
        data_quality = context.get_agent_result("data_quality")
        prediction = context.get_agent_result("prediction")
        recommendation = context.get_agent_result("recommendation")
        explainability = context.get_agent_result("explainability")

        if progress_callback:
            progress_callback("Processing metadata & statistics summaries...", 30)

        # Build sections
        metadata_sec = self._build_metadata_section(context, metadata)
        stats_mon_sec = self._build_stats_monitoring_section(context, statistics, monitoring)
        
        if progress_callback:
            progress_callback("Consolidating security & data quality findings...", 50)

        security_sec = self._build_security_section(context, security)
        quality_sec = self._build_quality_section(context, data_quality)
        query_sec = self._build_query_section(context, query_analysis)
        prediction_sec = self._build_prediction_section(context, prediction)

        if progress_callback:
            progress_callback("Compiling recommendations & explainability...", 75)

        recommendations_sec = self._build_recommendations_section(context, recommendation)
        explainability_sec = self._build_explainability_section(context, explainability)

        if progress_callback:
            progress_callback("Building executive summary...", 90)

        executive_summary = self._build_executive_summary(
            recommendations_sec=recommendations_sec,
            security_sec=security_sec,
            quality_sec=quality_sec,
            metadata_sec=metadata_sec,
        )

        report = {
            "warehouse_overview": {
                "warehouse_id": wh_info.get("id"),
                "name": wh_info.get("name"),
                "db_type": wh_info.get("db_type"),
                "host": wh_info.get("host"),
                "database_name": wh_info.get("database_name"),
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
            "executive_summary": executive_summary,
            "sections": {
                "metadata": metadata_sec,
                "statistics_monitoring": stats_mon_sec,
                "security": security_sec,
                "data_quality": quality_sec,
                "query_analysis": query_sec,
                "predictions": prediction_sec,
                "recommendations": recommendations_sec,
                "explainability": explainability_sec,
            }
        }

        if progress_callback:
            progress_callback("Report generation completed.", 100)

        return report

    # ── Section Builders ──────────────────────────────────────────

    def _build_metadata_section(self, context: SharedContext, metadata: Any) -> Dict[str, Any]:
        status = context.get_agent_status("metadata")
        status_str = status.value if status else ("COMPLETED" if metadata else "SKIPPED")

        if not metadata:
            return {
                "agent_status": status_str,
                "summary": "No metadata findings available in workflow state.",
                "schemas_count": 0,
                "tables_count": 0,
                "findings": [],
            }

        schemas = metadata.get("schemas", {})
        schemas_count = len(schemas)
        tables_count = sum(len(body.get("tables", {})) for body in schemas.values())

        findings = []
        for s_name, s_body in schemas.items():
            tables = s_body.get("tables", {})
            for t_name, t_body in tables.items():
                cols = t_body.get("columns", [])
                has_pk = any(c.get("primary_key") for c in cols)
                if not has_pk and cols:
                    findings.append(f"Schema '{s_name}': Table '{t_name}' ({len(cols)} cols) lacks a primary key constraint.")

        return {
            "agent_status": status_str,
            "summary": f"Discovered {schemas_count} schema(s) and {tables_count} table(s).",
            "schemas_count": schemas_count,
            "tables_count": tables_count,
            "findings": findings,
        }

    def _build_stats_monitoring_section(
        self, context: SharedContext, statistics: Any, monitoring: Any
    ) -> Dict[str, Any]:
        stats_status = context.get_agent_status("statistics")
        mon_status = context.get_agent_status("monitoring")
        status_str = stats_status.value if stats_status else ("COMPLETED" if statistics else "SKIPPED")

        if not statistics and not monitoring:
            return {
                "agent_status": status_str,
                "summary": "No statistics or monitoring findings available in workflow state.",
                "total_tables_analyzed": 0,
                "active_connections": None,
                "findings": [],
            }

        findings = []
        tables_analyzed = 0
        if statistics:
            tables = statistics.get("tables", [])
            tables_analyzed = len(tables)
            for t in tables:
                schema = t.get("schema", "")
                t_name = t.get("table_name", "")
                rows = t.get("estimated_row_count", 0)
                cols = t.get("total_columns", 0)
                if rows > 100000:
                    findings.append(f"Table '{schema}.{t_name}' contains high row volume ({rows:,} rows).")
                if cols > 20:
                    findings.append(f"Table '{schema}.{t_name}' is wide with {cols} columns.")

        active_conn = monitoring.get("active_connections") if monitoring else None
        if active_conn is not None:
            findings.append(f"Monitoring Agent recorded {active_conn} active database connections.")

        return {
            "agent_status": status_str,
            "summary": f"Analyzed volumetric statistics for {tables_analyzed} table(s).",
            "total_tables_analyzed": tables_analyzed,
            "active_connections": active_conn,
            "findings": findings,
        }

    def _build_security_section(self, context: SharedContext, security: Any) -> Dict[str, Any]:
        status = context.get_agent_status("security")
        status_str = status.value if status else ("COMPLETED" if security else "SKIPPED")

        if not security:
            return {
                "agent_status": status_str,
                "summary": "No security findings available in workflow state.",
                "total_issues": 0,
                "issues": [],
            }

        issues = security.get("issues", [])
        formatted_issues = []
        for issue in issues:
            formatted_issues.append({
                "severity": issue.get("severity", "MEDIUM"),
                "rule": issue.get("rule", "Security Issue"),
                "object": f"{issue.get('schema', '')}.{issue.get('table', '')}" + (f".{issue.get('column')}" if issue.get("column") else ""),
                "description": issue.get("description", ""),
            })

        return {
            "agent_status": status_str,
            "summary": f"Security analysis evaluated posture and identified {len(issues)} issue(s).",
            "total_issues": len(issues),
            "issues": formatted_issues,
        }

    def _build_quality_section(self, context: SharedContext, data_quality: Any) -> Dict[str, Any]:
        status = context.get_agent_status("data_quality")
        status_str = status.value if status else ("COMPLETED" if data_quality else "SKIPPED")

        if not data_quality:
            return {
                "agent_status": status_str,
                "summary": "No data quality findings available in workflow state.",
                "total_issues": 0,
                "issues": [],
            }

        issues = data_quality.get("issues", [])
        formatted_issues = []
        for issue in issues:
            formatted_issues.append({
                "severity": issue.get("severity", "MEDIUM"),
                "rule": issue.get("rule", "Data Quality Issue"),
                "object": f"{issue.get('schema', '')}.{issue.get('table', '')}" + (f".{issue.get('column')}" if issue.get("column") else ""),
                "dimension": issue.get("dimension", "completeness"),
            })

        return {
            "agent_status": status_str,
            "summary": f"Data quality analysis evaluated dimensions and identified {len(issues)} issue(s).",
            "total_issues": len(issues),
            "issues": formatted_issues,
        }

    def _build_query_section(self, context: SharedContext, query_analysis: Any) -> Dict[str, Any]:
        status = context.get_agent_status("query_analysis") or context.get_agent_status("query")
        status_str = status.value if status else ("COMPLETED" if query_analysis else "SKIPPED")

        if not query_analysis:
            return {
                "agent_status": status_str,
                "summary": "No query analysis findings available in workflow state.",
                "findings": [],
            }

        findings = query_analysis.get("findings", [])
        return {
            "agent_status": status_str,
            "summary": f"Query analysis evaluated query workload with {len(findings)} finding(s).",
            "findings": findings,
        }

    def _build_prediction_section(self, context: SharedContext, prediction: Any) -> Dict[str, Any]:
        status = context.get_agent_status("prediction")
        status_str = status.value if status else ("COMPLETED" if prediction else "SKIPPED")

        if not prediction:
            return {
                "agent_status": status_str,
                "summary": "No predictions available in workflow state.",
                "is_projection": True,
                "predictions": [],
            }

        insights = prediction.get("insights", [])
        return {
            "agent_status": status_str,
            "summary": "Predictive models generated projections based on trend data.",
            "is_projection": True,
            "predictions": insights,
        }

    def _build_recommendations_section(self, context: SharedContext, recommendation: Any) -> Dict[str, Any]:
        status = context.get_agent_status("recommendation")
        status_str = status.value if status else ("COMPLETED" if recommendation else "SKIPPED")

        if not recommendation:
            return {
                "agent_status": status_str,
                "summary": "No recommendations available in workflow state.",
                "total_recommendations": 0,
                "is_executed": False,
                "items": [],
            }

        recs = recommendation.get("recommendations", [])
        formatted_items = []
        for r in recs:
            formatted_items.append({
                "recommendation_type": r.get("recommendation_type"),
                "title": r.get("title"),
                "priority": r.get("priority", "MEDIUM"),
                "impact": r.get("impact", "MEDIUM"),
                "category": r.get("category", "General"),
                "object": f"{r.get('schema', '')}.{r.get('table', '')}" + (f".{r.get('column')}" if r.get("column") else ""),
                "description": r.get("description"),
                "status": "PROPOSED", # Explicitly PROPOSED, not executed
            })

        return {
            "agent_status": status_str,
            "summary": f"Generated {len(recs)} proposed recommendation(s).",
            "total_recommendations": len(recs),
            "is_executed": False,
            "items": formatted_items,
        }

    def _build_explainability_section(self, context: SharedContext, explainability: Any) -> Dict[str, Any]:
        status = context.get_agent_status("explainability")
        status_str = status.value if status else ("COMPLETED" if explainability else "SKIPPED")

        if not explainability:
            return {
                "agent_status": status_str,
                "summary": "No explainability evidence available in workflow state.",
                "explanation_count": 0,
                "items": [],
            }

        explanations = explainability.get("explanations", [])
        items = []
        for exp in explanations:
            items.append({
                "recommendation_type": exp.get("recommendation_type"),
                "title": exp.get("title"),
                "why": exp.get("why"),
                "evidence": exp.get("evidence", []),
                "supporting_agents": exp.get("supporting_agents", []),
            })

        return {
            "agent_status": status_str,
            "summary": f"Explainability Agent provided evidence for {len(explanations)} recommendation(s).",
            "explanation_count": len(explanations),
            "items": items,
        }

    def _build_executive_summary(
        self,
        recommendations_sec: Dict[str, Any],
        security_sec: Dict[str, Any],
        quality_sec: Dict[str, Any],
        metadata_sec: Dict[str, Any],
    ) -> Dict[str, Any]:
        recs = recommendations_sec.get("items", [])
        total_recs = len(recs)
        high_count = sum(1 for r in recs if r.get("priority") == "HIGH")
        med_count = sum(1 for r in recs if r.get("priority") == "MEDIUM")
        low_count = sum(1 for r in recs if r.get("priority") == "LOW")

        key_findings = []
        for r in recs[:5]: # Take top 5 key findings
            key_findings.append(f"{r.get('title')}: {r.get('description')}")

        return {
            "total_recommendations": total_recs,
            "severity_counts": {
                "HIGH": high_count,
                "MEDIUM": med_count,
                "LOW": low_count,
            },
            "security_issues_count": security_sec.get("total_issues", 0),
            "quality_issues_count": quality_sec.get("total_issues", 0),
            "tables_discovered": metadata_sec.get("tables_count", 0),
            "key_findings": key_findings if key_findings else ["No critical issues or recommendations detected."],
        }
