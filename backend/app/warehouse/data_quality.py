"""
Data quality analyzer.

Responsible for scanning warehouse tables to evaluate data quality
across core dimensions: completeness, uniqueness, validity, and consistency.
"""

from collections import defaultdict
from typing import Any

from app.models.warehouse import Warehouse
from app.context.shared_context import SharedContext
from app.core.config import settings

_HIGH = "HIGH"
_MEDIUM = "MEDIUM"
_LOW = "LOW"

_UNAVAILABLE_REASON = "unavailable (the current analyzer does not inspect row-level data)"

_DEDUCTIONS = {
    _HIGH: 10,
    _MEDIUM: 5,
    _LOW: 2,
}


class DataQualityAnalyzer:
    """
    Evaluates warehouse data quality dimensions using available metadata.
    """

    def analyse(self, warehouse: Warehouse, context: SharedContext, progress_callback: Any = None) -> dict[str, Any]:
        """
        Analyse the warehouse and return a data quality report.

        Parameters
        ──────────
        warehouse : Warehouse
            A registered ``Warehouse`` ORM instance.

        Returns
        ───────
        dict[str, Any]
            A dictionary containing the quality score, dimensions, and issues.
        """
        metadata = context.get_agent_result("metadata") or {}

        schemas = metadata.get("schemas", {})
        schema_keys = list(schemas.keys())
        total_schemas = len(schema_keys)

        issues = []
        recommendations = []

        # ── 1. Completeness ──────────────────────────────────────────
        if progress_callback: progress_callback("Inspecting nullable columns...", 10)

        for schema_idx, schema_name in enumerate(schema_keys):
            schema_body = schemas[schema_name]
            base_pct = 10 + int((schema_idx / max(total_schemas, 1)) * 20)
            
            for table_name, table_body in schema_body.get("tables", {}).items():
                columns = table_body.get("columns", [])
                total_cols = len(columns)
                if total_cols == 0:
                    continue

                nullable_cols = sum(1 for col in columns if col.get("nullable", True))
                ratio = nullable_cols / total_cols

                if ratio > settings.REC_NULLABLE_COLUMN_PCT:
                    issues.append({
                        "dimension": "completeness",
                        "severity": _MEDIUM,
                        "schema": schema_name,
                        "table": table_name,
                        "column": None,
                        "rule": "EXCESSIVE_TABLE_NULLABILITY",
                        "description": f"Table '{schema_name}.{table_name}' has a nullable_column_ratio of {ratio:.2f}, exceeding the threshold.",
                    })
                    recommendations.append({
                        "priority": _MEDIUM,
                        "category": "Data Quality",
                        "title": f"Reduce Nullability in {schema_name}.{table_name}",
                        "description": "Review the table schema and enforce NOT NULL constraints on mandatory fields.",
                    })

        completeness = {
            "completeness_rate": _UNAVAILABLE_REASON,
            "metric": "nullable_column_ratio used as structural completeness proxy.",
        }

        # ── 2. Uniqueness ────────────────────────────────────────────
        if progress_callback: progress_callback("Checking schema quality...", 35)

        for schema_idx, schema_name in enumerate(schema_keys):
            schema_body = schemas[schema_name]
            base_pct = 35 + int((schema_idx / max(total_schemas, 1)) * 20)
            
            for table_name, table_body in schema_body.get("tables", {}).items():
                columns = table_body.get("columns", [])
                has_pk = any(col.get("primary_key") for col in columns)
                
                if not has_pk and len(columns) > 0:
                    issues.append({
                        "dimension": "uniqueness",
                        "severity": _MEDIUM,
                        "schema": schema_name,
                        "table": table_name,
                        "column": None,
                        "rule": "MISSING_UNIQUENESS_CONSTRAINTS",
                        "description": f"Table '{schema_name}.{table_name}' lacks a primary key or uniqueness enforcement mechanism. (No actual duplicate rows were inspected).",
                    })
                    recommendations.append({
                        "priority": _MEDIUM,
                        "category": "Data Quality",
                        "title": f"Add Primary Key to {schema_name}.{table_name}",
                        "description": "Define a primary key to enforce uniqueness structurally.",
                    })

        uniqueness = {
            "duplicate_record_rate": _UNAVAILABLE_REASON,
        }

        # ── 3. Validity ──────────────────────────────────────────────
        if progress_callback: progress_callback("Checking datatype consistency...", 60)

        for schema_idx, schema_name in enumerate(schema_keys):
            schema_body = schemas[schema_name]
            base_pct = 60 + int((schema_idx / max(total_schemas, 1)) * 20)
            
            for table_name, table_body in schema_body.get("tables", {}).items():
                columns = table_body.get("columns", [])
                for col in columns:
                    cname = col.get("name", "")
                    ctype = str(col.get("type", "")).strip().upper()

                    if not ctype or ctype in {"UNKNOWN", "USER-DEFINED", "NULL", "NONE"}:
                        issues.append({
                            "dimension": "validity",
                            "severity": _MEDIUM,
                            "schema": schema_name,
                            "table": table_name,
                            "column": cname,
                            "rule": "INVALID_OR_UNKNOWN_DATATYPE",
                            "description": f"Column '{cname}' in '{schema_name}.{table_name}' has an unknown or missing data type: '{ctype}'.",
                        })
                        recommendations.append({
                            "priority": _MEDIUM,
                            "category": "Data Quality",
                            "title": f"Fix Datatype for {schema_name}.{table_name}.{cname}",
                            "description": "Define a standard explicit datatype to ensure downstream validity.",
                        })

        validity = {
            "format_compliance_rate": _UNAVAILABLE_REASON,
        }

        # ── 4. Consistency ───────────────────────────────────────────
        if progress_callback: progress_callback("Inspecting duplicate patterns...", 85)

        col_type_map = defaultdict(list)
        for schema_name, schema_body in schemas.items():
            for table_name, table_body in schema_body.get("tables", {}).items():
                for col in table_body.get("columns", []):
                    cname = col.get("name", "")
                    ctype = str(col.get("type", "")).strip().upper()
                    if cname and ctype:
                        col_type_map[cname].append((schema_name, table_name, ctype))

        for cname, occurrences in col_type_map.items():
            if len(occurrences) > 1:
                types = {ctype for _, _, ctype in occurrences}
                if len(types) > 1:
                    locations = ", ".join(f"{s}.{t} ({c})" for s, t, c in occurrences)
                    issues.append({
                        "dimension": "consistency",
                        "severity": _MEDIUM,
                        "schema": "multiple",
                        "table": "multiple",
                        "column": cname,
                        "rule": "INCONSISTENT_DATATYPES",
                        "description": f"Column '{cname}' has inconsistent datatypes across tables: {locations}",
                    })
                    recommendations.append({
                        "priority": _MEDIUM,
                        "category": "Data Quality",
                        "title": f"Standardize Datatype for '{cname}'",
                        "description": "Align the datatype of this column identically across all tables to ensure structural consistency.",
                    })

        consistency = {
            "structural_consistency_rate": _UNAVAILABLE_REASON,
        }

        # ── Scoring ──────────────────────────────────────────────────
        if progress_callback: progress_callback("Generating data-quality findings...", 95)

        score = 100
        for issue in issues:
            score -= _DEDUCTIONS.get(issue["severity"], 0)

        score = max(0, score)

        if score >= 90:
            level = "EXCELLENT"
        elif score >= 75:
            level = "GOOD"
        elif score >= 50:
            level = "FAIR"
        else:
            level = "POOR"

        return {
            "summary": {
                "quality_score": score,
                "quality_level": level,
                "issue_count": len(issues),
            },
            "dimensions": {
                "completeness": completeness,
                "uniqueness": uniqueness,
                "validity": validity,
                "consistency": consistency,
            },
            "issues": issues,
            "recommendations": recommendations,
        }
