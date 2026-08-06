"""
Warehouse security analyser.

Performs a **rule-based static security analysis** of a registered
data warehouse by inspecting the structural metadata previously
discovered by :class:`~app.agents.metadata_agent.MetadataAgent` and
stored in the shared memory bus (:class:`~app.context.shared_context.SharedContext`).

.. important::

    This analyser executes **zero SQL queries**.  All information is
    derived exclusively from the metadata snapshot already present in
    ``SharedContext`` under the key ``"metadata"``.  Running
    :class:`~app.agents.metadata_agent.MetadataAgent` before this
    analyser is therefore a hard prerequisite.

Analysis rules
──────────────
* **Rule 1 — Sensitive Columns** (HIGH)
    Detects column names that likely contain personally-identifiable or
    confidential data (passwords, tokens, national IDs, etc.).

* **Rule 2 — Missing Primary Key** (HIGH)
    Tables that have no column marked as a primary key are flagged as
    structurally unsound — they cannot reliably enforce uniqueness and
    are harder to audit.

* **Rule 3 — Nullable Sensitive Columns** (MEDIUM)
    A sensitive column that accepts ``NULL`` values weakens data-quality
    guarantees and may indicate that the constraint model was not
    properly reviewed.

* **Rule 4 — Weak Table Names** (LOW)
    Generic or placeholder table names (``temp``, ``test``, ``tbl``, …)
    suggest the schema was not named with production intent in mind.

* **Rule 5 — Weak Column Names** (LOW)
    Generic column names (``col1``, ``field``, ``data``, …) make the
    data model harder to understand and audit.

No LLM calls, no SQL execution, no HTTP concerns, no orchestration
logic.
"""

from __future__ import annotations

from typing import Any

from app.context.shared_context import SharedContext
from app.models.warehouse import Warehouse


# ── Severity constants ───────────────────────────────────────────

_HIGH   = "HIGH"
_MEDIUM = "MEDIUM"
_LOW    = "LOW"

# ── Point deductions per severity ────────────────────────────────

_DEDUCTION: dict[str, int] = {
    _HIGH:   10,
    _MEDIUM:  5,
    _LOW:     2,
}

# ── Sensitive column name keywords (lower-cased) ─────────────────

_SENSITIVE_KEYWORDS: frozenset[str] = frozenset({
    "password", "passwd", "pwd",
    "token", "secret", "api_key",
    "email", "phone", "mobile",
    "ssn", "aadhaar", "pan",
    "credit_card",
})

# ── Weak table name patterns (lower-cased, exact match) ──────────

_WEAK_TABLE_NAMES: frozenset[str] = frozenset({
    "tbl", "table1", "temp", "data",
    "test", "sample", "abc", "xyz",
})

# ── Weak column name patterns (lower-cased, exact match) ─────────

_WEAK_COLUMN_NAMES: frozenset[str] = frozenset({
    "col1", "col2", "field",
    "value", "data", "temp", "abc",
})

# ── System schemas (excluded by default) ─────────────────────────

_SYSTEM_SCHEMAS: frozenset[str] = frozenset({
    "information_schema", "pg_catalog", "pg_toast"
})

def _is_system_schema(schema_name: str) -> bool:
    """Check if a schema is a known PostgreSQL system schema."""
    return schema_name in _SYSTEM_SCHEMAS or schema_name.startswith("pg_temp")


# ── Analyser ─────────────────────────────────────────────────────


class SecurityAnalyzer:
    """
    Performs static, rule-based security analysis of a data warehouse.

    The analyser reads the metadata snapshot from
    :class:`~app.context.shared_context.SharedContext` — populated
    previously by :class:`~app.agents.metadata_agent.MetadataAgent` —
    and applies a set of configurable rules to produce a structured
    security report.

    .. note::

        **Prerequisite**: ``MetadataAgent.discover_metadata()`` must
        have been executed (and its result stored in ``SharedContext``)
        before calling :meth:`analyse`.  If the metadata is absent, the
        report is returned with a note in the ``summary``.

    Usage::

        analyzer = SecurityAnalyzer()
        report   = analyzer.analyse(warehouse)
    """

    # ── Public API ───────────────────────────────────────────────

    def analyse(self, warehouse: Warehouse, include_system_schemas: bool = False) -> dict[str, Any]:
        """
        Run all security rules against the warehouse metadata and
        return a structured security report.

        Parameters
        ──────────
        warehouse : Warehouse
            A registered, active ``Warehouse`` ORM instance.  Used
            only for identity information (``id``, ``name``) embedded
            in the report — no live connection is made.
        include_system_schemas : bool
            If True, overrides default behavior and includes system
            schemas in the security analysis. Defaults to False.

        Returns
        ───────
        dict[str, Any]
            A report with the following top-level keys::

                {
                    "risk_score":      int,           # 0–100
                    "risk_level":      str,           # "LOW" | "MEDIUM" | "HIGH"
                    "summary": {
                        "tables_analyzed": int,
                        "issues_found":    int,
                        "high":            int,
                        "medium":          int,
                        "low":             int,
                    },
                    "issues": [
                        {
                            "rule":        str,
                            "severity":    str,   # "HIGH" | "MEDIUM" | "LOW"
                            "schema":      str,
                            "table":       str,
                            "column":      str | None,
                            "description": str,
                        },
                        ...
                    ],
                    "recommendations": [str, ...],
                }
        """
        metadata = SharedContext().get_agent_result("metadata")
        issues: list[dict[str, Any]] = []

        if metadata:
            schemas: dict[str, Any] = metadata.get("schemas", {})
            for schema_name, schema_body in schemas.items():
                if not include_system_schemas and _is_system_schema(schema_name):
                    continue

                tables: dict[str, Any] = schema_body.get("tables", {})
                for table_name, table_body in tables.items():
                    columns: list[dict[str, Any]] = table_body.get("columns", [])
                    issues.extend(
                        self._check_sensitive_columns(schema_name, table_name, columns)
                    )
                    issues.extend(
                        self._check_missing_primary_key(schema_name, table_name, columns)
                    )
                    issues.extend(
                        self._check_nullable_sensitive_columns(schema_name, table_name, columns)
                    )
                    issues.extend(
                        self._check_weak_table_name(schema_name, table_name)
                    )
                    issues.extend(
                        self._check_weak_column_names(schema_name, table_name, columns)
                    )

        summary    = self._build_summary(metadata, issues)
        risk_score = self._calculate_risk_score(issues)
        risk_level = self._classify_risk(risk_score)
        recommendations = self._build_recommendations(issues)

        return {
            "risk_score":      risk_score,
            "risk_level":      risk_level,
            "summary":         summary,
            "issues":          issues,
            "recommendations": recommendations,
        }

    # ── Rule 1 — Sensitive column detection ──────────────────────

    @staticmethod
    def _check_sensitive_columns(
        schema: str,
        table: str,
        columns: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        Detect columns whose names suggest they hold sensitive data.

        A column name is considered sensitive when it matches (case-
        insensitively) any entry in :data:`_SENSITIVE_KEYWORDS`.

        Parameters
        ──────────
        schema  : str
            The schema that owns this table.
        table   : str
            The table being inspected.
        columns : list[dict[str, Any]]
            Column descriptors as returned by the metadata inspector.

        Returns
        ───────
        list[dict[str, Any]]
            Zero or more HIGH-severity issue records.
        """
        issues: list[dict[str, Any]] = []

        for col in columns:
            col_name: str = col.get("name", "")
            if col_name.lower() in _SENSITIVE_KEYWORDS:
                issues.append({
                    "rule":        "SENSITIVE_COLUMN",
                    "severity":    _HIGH,
                    "schema":      schema,
                    "table":       table,
                    "column":      col_name,
                    "description": (
                        f"Column '{col_name}' in '{schema}.{table}' appears to "
                        "store sensitive data and should be encrypted or masked."
                    ),
                })

        return issues

    # ── Rule 2 — Missing primary key ─────────────────────────────

    @staticmethod
    def _check_missing_primary_key(
        schema: str,
        table: str,
        columns: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        Flag tables that have no primary-key column.

        The metadata inspector records column-level ``primary_key``
        flags.  A table is considered to lack a primary key when none
        of its columns carry that flag set to a truthy value.

        Parameters
        ──────────
        schema  : str
            The schema that owns this table.
        table   : str
            The table being inspected.
        columns : list[dict[str, Any]]
            Column descriptors as returned by the metadata inspector.

        Returns
        ───────
        list[dict[str, Any]]
            Zero or one HIGH-severity issue record.
        """
        has_pk = any(col.get("primary_key") for col in columns)
        if has_pk or not columns:
            return []

        return [{
            "rule":        "MISSING_PRIMARY_KEY",
            "severity":    _HIGH,
            "schema":      schema,
            "table":       table,
            "column":      None,
            "description": (
                f"Table '{schema}.{table}' has no primary key.  "
                "Rows cannot be uniquely identified, which undermines "
                "data integrity and audit trails."
            ),
        }]

    # ── Rule 3 — Nullable sensitive columns ───────────────────────

    @staticmethod
    def _check_nullable_sensitive_columns(
        schema: str,
        table: str,
        columns: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        Flag sensitive columns that accept ``NULL`` values.

        Sensitive data columns should typically be ``NOT NULL`` to
        enforce data-quality guarantees; a nullable sensitive column
        may indicate the constraint model was not reviewed.

        Parameters
        ──────────
        schema  : str
            The schema that owns this table.
        table   : str
            The table being inspected.
        columns : list[dict[str, Any]]
            Column descriptors as returned by the metadata inspector.

        Returns
        ───────
        list[dict[str, Any]]
            Zero or more MEDIUM-severity issue records.
        """
        issues: list[dict[str, Any]] = []

        for col in columns:
            col_name: str = col.get("name", "")
            is_sensitive = col_name.lower() in _SENSITIVE_KEYWORDS
            is_nullable  = col.get("nullable", True)

            if is_sensitive and is_nullable:
                issues.append({
                    "rule":        "NULLABLE_SENSITIVE_COLUMN",
                    "severity":    _MEDIUM,
                    "schema":      schema,
                    "table":       table,
                    "column":      col_name,
                    "description": (
                        f"Sensitive column '{col_name}' in '{schema}.{table}' "
                        "allows NULL values.  Consider adding a NOT NULL "
                        "constraint to strengthen data-quality guarantees."
                    ),
                })

        return issues

    # ── Rule 4 — Weak table names ─────────────────────────────────

    @staticmethod
    def _check_weak_table_name(
        schema: str,
        table: str,
    ) -> list[dict[str, Any]]:
        """
        Flag tables whose names match known generic/placeholder patterns.

        Generic table names (e.g. ``temp``, ``test``, ``tbl``) suggest
        the schema may not have been designed with production standards
        in mind.

        Parameters
        ──────────
        schema : str
            The schema that owns this table.
        table  : str
            The table name to evaluate.

        Returns
        ───────
        list[dict[str, Any]]
            Zero or one LOW-severity issue record.
        """
        if table.lower() not in _WEAK_TABLE_NAMES:
            return []

        return [{
            "rule":        "WEAK_TABLE_NAME",
            "severity":    _LOW,
            "schema":      schema,
            "table":       table,
            "column":      None,
            "description": (
                f"Table name '{table}' in schema '{schema}' is generic or "
                "placeholder-like.  Rename it to reflect its business purpose."
            ),
        }]

    # ── Rule 5 — Weak column names ────────────────────────────────

    @staticmethod
    def _check_weak_column_names(
        schema: str,
        table: str,
        columns: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        Flag columns whose names match known generic/placeholder patterns.

        Generic column names (e.g. ``col1``, ``field``, ``data``) make
        the data model opaque and harder to audit or document.

        Parameters
        ──────────
        schema  : str
            The schema that owns this table.
        table   : str
            The table being inspected.
        columns : list[dict[str, Any]]
            Column descriptors as returned by the metadata inspector.

        Returns
        ───────
        list[dict[str, Any]]
            Zero or more LOW-severity issue records.
        """
        issues: list[dict[str, Any]] = []

        for col in columns:
            col_name: str = col.get("name", "")
            if col_name.lower() in _WEAK_COLUMN_NAMES:
                issues.append({
                    "rule":        "WEAK_COLUMN_NAME",
                    "severity":    _LOW,
                    "schema":      schema,
                    "table":       table,
                    "column":      col_name,
                    "description": (
                        f"Column name '{col_name}' in '{schema}.{table}' is "
                        "too generic.  Rename it to something meaningful that "
                        "reflects the data it stores."
                    ),
                })

        return issues

    # ── Rule 6 — Summary ─────────────────────────────────────────

    @staticmethod
    def _build_summary(
        metadata: dict[str, Any] | None,
        issues: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Compute aggregate counts from discovered issues.

        Parameters
        ──────────
        metadata : dict[str, Any] | None
            The raw metadata snapshot from ``SharedContext``.
        issues   : list[dict[str, Any]]
            All issue records produced by the rule checks.

        Returns
        ───────
        dict[str, Any]
            Summary containing table count and per-severity tallies.
        """
        tables_analyzed = 0
        if metadata:
            for schema_body in metadata.get("schemas", {}).values():
                tables_analyzed += len(schema_body.get("tables", {}))

        high   = sum(1 for i in issues if i["severity"] == _HIGH)
        medium = sum(1 for i in issues if i["severity"] == _MEDIUM)
        low    = sum(1 for i in issues if i["severity"] == _LOW)

        return {
            "tables_analyzed": tables_analyzed,
            "issues_found":    len(issues),
            "high":            high,
            "medium":          medium,
            "low":             low,
        }

    # ── Rule 7 — Risk score ───────────────────────────────────────

    @staticmethod
    def _calculate_risk_score(issues: list[dict[str, Any]]) -> int:
        """
        Derive a 0–100 risk score from the discovered issues.

        Each issue deducts points from a perfect score of 100 according
        to its severity:

        * HIGH   → 10 points
        * MEDIUM →  5 points
        * LOW    →  2 points

        The score is clamped to zero — it cannot go negative.

        Parameters
        ──────────
        issues : list[dict[str, Any]]
            All issue records produced by the rule checks.

        Returns
        ───────
        int
            A score in the range [0, 100]; higher is better.
        """
        deductions = sum(_DEDUCTION.get(i["severity"], 0) for i in issues)
        return max(0, 100 - deductions)

    @staticmethod
    def _classify_risk(risk_score: int) -> str:
        """
        Map a numeric risk score to a human-readable risk level.

        Thresholds
        ──────────
        * 80–100 → ``"LOW"``
        * 50–79  → ``"MEDIUM"``
        * 0–49   → ``"HIGH"``

        Parameters
        ──────────
        risk_score : int
            The score produced by :meth:`_calculate_risk_score`.

        Returns
        ───────
        str
            One of ``"LOW"``, ``"MEDIUM"``, or ``"HIGH"``.
        """
        if risk_score >= 80:
            return _LOW
        if risk_score >= 50:
            return _MEDIUM
        return _HIGH

    # ── Rule 8 — Recommendations ─────────────────────────────────

    @staticmethod
    def _build_recommendations(issues: list[dict[str, Any]]) -> list[str]:
        """
        Derive a de-duplicated set of actionable recommendations from
        the discovered issues.

        Each unique rule type found in the issue list maps to a single
        recommendation string.  Duplicates are suppressed so the output
        remains concise regardless of how many tables trigger the same
        rule.

        Parameters
        ──────────
        issues : list[dict[str, Any]]
            All issue records produced by the rule checks.

        Returns
        ───────
        list[str]
            An ordered list of unique recommendation messages.
        """
        _RECOMMENDATION_MAP: dict[str, str] = {
            "SENSITIVE_COLUMN": (
                "Encrypt or mask sensitive columns (passwords, tokens, "
                "personal identifiers) using appropriate column-level "
                "encryption or data-masking policies."
            ),
            "MISSING_PRIMARY_KEY": (
                "Add a primary key to every table to enforce row uniqueness, "
                "enable reliable foreign-key references, and support auditing."
            ),
            "NULLABLE_SENSITIVE_COLUMN": (
                "Mark sensitive columns as NOT NULL where the business domain "
                "guarantees a value is always present, strengthening data-"
                "quality and reducing exposure to incomplete records."
            ),
            "WEAK_TABLE_NAME": (
                "Rename generic or placeholder table names (e.g. 'temp', "
                "'test', 'tbl') to descriptive names that reflect their "
                "business purpose and intended lifespan."
            ),
            "WEAK_COLUMN_NAME": (
                "Rename generic column names (e.g. 'col1', 'field', 'data') "
                "to meaningful identifiers that clearly communicate the data "
                "they store."
            ),
        }

        seen_rules: set[str] = set()
        recommendations: list[str] = []

        for issue in issues:
            rule = issue.get("rule", "")
            if rule not in seen_rules and rule in _RECOMMENDATION_MAP:
                recommendations.append(_RECOMMENDATION_MAP[rule])
                seen_rules.add(rule)

        return recommendations
