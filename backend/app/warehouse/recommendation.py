"""
Warehouse recommendation engine.

Analyzes the warehouse by consuming metadata, security, and statistics
outputs from the shared memory bus and produces deterministic, rule-based
actionable recommendations.

No SQL execution, no database writes, no HTTP, no LLMs.
"""

from typing import Any

from app.models.warehouse import Warehouse
from app.context.shared_context import SharedContext
from app.core.config import settings


# ── Constants ────────────────────────────────────────────────────────

_HIGH = "HIGH"
_MEDIUM = "MEDIUM"
_LOW = "LOW"

_WEAK_TABLE_NAMES = frozenset({"temp", "test", "tbl", "data", "backup"})
_WEAK_COLUMN_NAMES = frozenset({"col1", "col2", "field", "value", "data"})


class RecommendationEngine:
    """
    Rule-based engine for generating recommendations based on previous
    agent analysis results.
    """

    def __init__(self) -> None:
        """Initialize the rule registry for dynamic recommendation generation."""
        self._registry = {
            "metadata": self._generate_metadata_recommendations,
            "statistics": self._generate_statistics_recommendations,
            "security": self._generate_security_recommendations,
        }

    def analyse(self, warehouse: Warehouse) -> dict[str, Any]:
        """
        Analyse the warehouse and return recommendations.

        Parameters
        ──────────
        warehouse : Warehouse
            A registered ``Warehouse`` ORM instance.

        Returns
        ───────
        dict[str, Any]
            A dictionary containing summary, recommendations, and priority.
        """
        context = SharedContext()
        recommendations: list[dict[str, Any]] = []

        for agent_key, rule_generator in self._registry.items():
            agent_result = context.get_agent_result(agent_key) or {}
            recommendations.extend(rule_generator(agent_result))

        recommendations = self._deduplicate_recommendations(recommendations)

        priority_order = {_HIGH: 0, _MEDIUM: 1, _LOW: 2}
        category_order = {"Security": 0, "Metadata": 1, "Statistics": 2}
        
        recommendations.sort(
            key=lambda r: (
                priority_order.get(r["priority"], 99),
                category_order.get(r["category"], 99),
            )
        )

        summary = {
            "recommendation_count": len(recommendations),
            "high": sum(1 for r in recommendations if r["priority"] == _HIGH),
            "medium": sum(1 for r in recommendations if r["priority"] == _MEDIUM),
            "low": sum(1 for r in recommendations if r["priority"] == _LOW),
        }

        priority = {
            "high": [r for r in recommendations if r["priority"] == _HIGH],
            "medium": [r for r in recommendations if r["priority"] == _MEDIUM],
            "low": [r for r in recommendations if r["priority"] == _LOW],
        }

        return {
            "summary": summary,
            "recommendations": recommendations,
            "priority": priority,
        }

    # ── Metadata Rules ───────────────────────────────────────────

    def _generate_metadata_recommendations(
        self, metadata: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """
        Generate recommendations based on metadata structure.
        """
        recs: list[dict[str, Any]] = []
        schemas = metadata.get("schemas", {})

        for schema_name, schema_body in schemas.items():
            tables = schema_body.get("tables", {})
            for table_name, table_body in tables.items():
                columns = table_body.get("columns", [])
                
                # Rule: Missing Primary Key
                has_pk = any(col.get("primary_key") for col in columns)
                if not has_pk and columns:
                    recs.append(self._build_recommendation(
                        recommendation_type="missing_primary_key",
                        schema=schema_name,
                        table=table_name,
                        column=None,
                        priority=_HIGH,
                        impact=_HIGH,
                        effort=_LOW,
                        confidence=1.0,
                        category="Metadata",
                        title=f"Missing Primary Key on {schema_name}.{table_name}",
                        description=f"Table '{schema_name}.{table_name}' lacks a primary key. Add one to ensure row uniqueness.",
                        source="metadata",
                    ))
                
                # Rule: Weak Table Name
                if table_name.lower() in _WEAK_TABLE_NAMES:
                    recs.append(self._build_recommendation(
                        recommendation_type="weak_table_name",
                        schema=schema_name,
                        table=table_name,
                        column=None,
                        priority=_LOW,
                        impact=_LOW,
                        effort=_LOW,
                        confidence=0.9,
                        category="Metadata",
                        title=f"Weak Table Name: {table_name}",
                        description=f"The table '{schema_name}.{table_name}' has a generic name. Consider renaming it.",
                        source="metadata",
                    ))

                # Rule: Weak Column Name
                for col in columns:
                    col_name = col.get("name", "")
                    if col_name.lower() in _WEAK_COLUMN_NAMES:
                        recs.append(self._build_recommendation(
                            recommendation_type="weak_column_name",
                            schema=schema_name,
                            table=table_name,
                            column=col_name,
                            priority=_LOW,
                            impact=_LOW,
                            effort=_LOW,
                            confidence=0.9,
                            category="Metadata",
                            title=f"Weak Column Name: {col_name} in {table_name}",
                            description=f"Column '{col_name}' in '{schema_name}.{table_name}' has a generic name.",
                            source="metadata",
                        ))

        return recs

    # ── Statistics Rules ─────────────────────────────────────────

    def _generate_statistics_recommendations(
        self, statistics: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """
        Generate recommendations based on data volume and metrics.
        """
        recs: list[dict[str, Any]] = []
        tables = statistics.get("tables", [])

        for t in tables:
            schema = t.get("schema", "")
            table_name = t.get("table_name", "")
            rows = t.get("estimated_row_count", 0)
            cols = t.get("total_columns", 0)

            # Rule: Large Table Indexing
            if rows > settings.REC_LARGE_TABLE_ROWS:
                recs.append(self._build_recommendation(
                    recommendation_type="large_table_indexing",
                    schema=schema,
                    table=table_name,
                    column=None,
                    priority=_MEDIUM,
                    impact=_MEDIUM,
                    effort=_MEDIUM,
                    confidence=0.9,
                    category="Statistics",
                    title=f"Large Table: {schema}.{table_name}",
                    description=f"Table '{schema}.{table_name}' has {rows} rows. Ensure appropriate indexes are in place to support query performance.",
                    source="statistics",
                ))
            # Rule: Empty Table Archiving
            elif rows <= settings.REC_EMPTY_TABLE_ROWS:
                from datetime import datetime, timezone, timedelta
                
                _IGNORED_EMPTY_TABLES = {"alembic_version", "flyway_schema_history", "django_migrations"}
                is_ignored = table_name.lower() in _IGNORED_EMPTY_TABLES or "config" in table_name.lower() or "setting" in table_name.lower()
                
                is_recent = False
                if "created_at" in t and isinstance(t["created_at"], str):
                    try:
                        created_dt = datetime.fromisoformat(t["created_at"].replace("Z", "+00:00"))
                        if datetime.now(timezone.utc) - created_dt < timedelta(days=1):
                            is_recent = True
                    except ValueError:
                        pass
                
                if not is_ignored and not is_recent:
                    recs.append(self._build_recommendation(
                        recommendation_type="empty_table",
                        schema=schema,
                        table=table_name,
                        column=None,
                        priority=_LOW,
                        impact=_LOW,
                        effort=_LOW,
                        confidence=0.8,
                        category="Statistics",
                        title=f"Empty Table: {schema}.{table_name}",
                        description=f"Table '{schema}.{table_name}' is empty. Consider archiving or dropping it if it is genuinely unused.",
                        source="statistics",
                    ))

            # Rule: Unusually Wide Table
            if cols > settings.REC_WIDE_TABLE_COLS:
                recs.append(self._build_recommendation(
                    recommendation_type="wide_table",
                    schema=schema,
                    table=table_name,
                    column=None,
                    priority=_MEDIUM,
                    impact=_MEDIUM,
                    effort=_HIGH,
                    confidence=0.9,
                    category="Statistics",
                    title=f"Wide Table: {schema}.{table_name}",
                    description=f"Table '{schema}.{table_name}' has {cols} columns. Consider normalizing it to improve maintainability.",
                    source="statistics",
                ))

        return recs

    # ── Security Rules ───────────────────────────────────────────

    def _generate_security_recommendations(
        self, security: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """
        Convert existing security issues into actionable recommendations.
        """
        recs: list[dict[str, Any]] = []
        issues = security.get("issues", [])

        for issue in issues:
            severity = issue.get("severity", _MEDIUM)
            rule = issue.get("rule", "Security Issue")
            desc = issue.get("description", "A security issue was detected.")
            schema = issue.get("schema", "unknown")
            table = issue.get("table", "unknown")
            column = issue.get("column", None)
            
            recs.append(self._build_recommendation(
                recommendation_type=rule.lower().replace(" ", "_").replace("-", "_"),
                schema=schema,
                table=table,
                column=column,
                priority=severity,
                impact=severity,
                effort=_MEDIUM,
                confidence=1.0,
                category="Security",
                title=f"Security Alert: {rule} on {schema}.{table}",
                description=desc,
                source="security",
            ))
            
        return recs

    # ── Helper ───────────────────────────────────────────────────

    @staticmethod
    def _deduplicate_recommendations(
        recommendations: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        Merge recommendations with the same semantic meaning.
        """
        merged: dict[tuple[str, str, str, str | None], dict[str, Any]] = {}
        for rec in recommendations:
            key = (
                rec.get("recommendation_type", ""),
                rec.get("schema", ""),
                rec.get("table", ""),
                rec.get("column")
            )
            if key not in merged:
                merged[key] = dict(rec)
                merged[key]["source_agents"] = list(rec["source_agents"])
            else:
                for agent in rec["source_agents"]:
                    if agent not in merged[key]["source_agents"]:
                        merged[key]["source_agents"].append(agent)
                        
        return list(merged.values())

    @staticmethod
    def _build_recommendation(
        recommendation_type: str,
        schema: str,
        table: str,
        column: str | None,
        priority: str,
        impact: str,
        effort: str,
        confidence: float,
        category: str,
        title: str,
        description: str,
        source: str,
    ) -> dict[str, Any]:
        """
        Format a single recommendation dictionary.
        """
        return {
            "recommendation_type": recommendation_type,
            "schema": schema,
            "table": table,
            "column": column,
            "priority": priority,
            "impact": impact,
            "effort": effort,
            "confidence": confidence,
            "category": category,
            "title": title,
            "description": description,
            "source_agents": [source],
        }
