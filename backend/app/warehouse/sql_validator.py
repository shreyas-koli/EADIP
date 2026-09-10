"""
SQL Safety Validator for the AetherArchive SQL Console.

This module is the FIRST line of defence. It uses sqlparse to parse and
analyse submitted SQL before it ever reaches the database connection.

Security design (defence-in-depth):

    User SQL
        ↓  1. sqlparse structural analysis  ← this module
        ↓  2. Read-only PostgreSQL transaction  ← executed in explorer.py
        ↓  3. statement_timeout  ← executed in explorer.py
        ↓  4. Fetch cap (MAX_QUERY_ROWS)  ← executed in explorer.py
        ↓
    PostgreSQL
"""

from __future__ import annotations

import sqlparse
from sqlparse.sql import Statement
from sqlparse.tokens import Keyword, DDL, DML


# ── Allowed DML/Statement types ──────────────────────────────────────────────
# Only read-oriented statement types are permitted.
_ALLOWED_DML_KEYWORDS: frozenset[str] = frozenset(
    {"SELECT", "WITH"}
)
_ALLOWED_STATEMENT_TYPES: frozenset[str] = frozenset(
    {"SELECT", "EXPLAIN", "SHOW"}
)

# ── Blocked statement-level keywords ─────────────────────────────────────────
# This list is belt-and-suspenders; the read-only transaction is the real guard.
_BLOCKED_KEYWORDS: frozenset[str] = frozenset(
    {
        # Write DML
        "INSERT", "UPDATE", "DELETE", "MERGE", "UPSERT", "REPLACE",
        # DDL
        "CREATE", "DROP", "ALTER", "TRUNCATE", "RENAME",
        # DCL / privilege
        "GRANT", "REVOKE",
        # Misc
        "COMMENT", "VACUUM", "CALL", "DO",
        # Transaction control
        "BEGIN", "COMMIT", "ROLLBACK", "SAVEPOINT", "RELEASE",
        "START",  # START TRANSACTION
        "SET",    # SET SESSION/LOCAL can mutate session state
        "LOCK",
        "COPY",
        "IMPORT",
        "LOAD",
        "ATTACH",
        "DETACH",
    }
)


class SQLValidationError(ValueError):
    """Raised when submitted SQL fails the safety policy."""


def validate_sql(raw_sql: str) -> str:
    """
    Validate that *raw_sql* is a single, safe, read-only SQL statement.

    Returns the normalised SQL string on success.
    Raises SQLValidationError with a user-friendly message on failure.

    Strategy:
    1. Strip and check for empty input.
    2. Parse with sqlparse.
    3. Reject multi-statement input.
    4. Inspect the first (and only) statement for blocked keywords.
    5. Confirm the statement type is in the allowed set.
    """
    sql = raw_sql.strip()
    if not sql:
        raise SQLValidationError("SQL query cannot be empty.")

    # Remove trailing semicolons before parsing to allow single-statement
    # queries that end with ";".
    sql_stripped = sql.rstrip(";").strip()

    # ── Multi-statement detection ─────────────────────────────────────────
    # sqlparse.split() splits on ; while respecting quoted strings and
    # dollar-quoted blocks.  Any non-empty second statement is rejected.
    statements = [s.strip() for s in sqlparse.split(sql_stripped) if s.strip()]
    if len(statements) == 0:
        raise SQLValidationError("SQL query cannot be empty.")
    if len(statements) > 1:
        raise SQLValidationError(
            "Only a single SQL statement is allowed per request. "
            "Multiple statements are not permitted."
        )

    parsed: Statement = sqlparse.parse(statements[0])[0]

    # ── Blocked keyword scan ─────────────────────────────────────────────
    # Walk every token; surface-level keyword check.
    for token in parsed.flatten():
        ttype = token.ttype
        val = token.normalized.upper()

        if ttype in (Keyword, DDL, DML) or ttype in Keyword:
            if val in _BLOCKED_KEYWORDS:
                raise SQLValidationError(
                    f"Only read-only SQL queries are allowed. "
                    f"The keyword '{val}' is not permitted."
                )

    # ── Statement type allowlist ─────────────────────────────────────────
    stmt_type = parsed.get_type()  # returns None, SELECT, INSERT, UNKNOWN, etc.
    
    if stmt_type == "UNKNOWN":
        # sqlparse sometimes categorises EXPLAIN as UNKNOWN.
        # If the query starts with EXPLAIN, it's an explain query.
        # It's safe to allow it because our _BLOCKED_KEYWORDS scan above
        # has already ensured no write keywords (like UPDATE) are present anywhere.
        first_token = parsed.token_first(skip_ws=True, skip_cm=True)
        if first_token and first_token.normalized.upper() == "EXPLAIN":
            pass  # Allowed
        else:
            raise SQLValidationError(
                f"Only read-only SQL queries are allowed. "
                f"Statement type '{stmt_type}' is not permitted."
            )
    elif stmt_type is None:
        # sqlparse cannot always classify e.g. WITH.
        # Fall through — the read-only transaction provides the real guard.
        pass
    elif stmt_type.upper() not in _ALLOWED_STATEMENT_TYPES:
        raise SQLValidationError(
            f"Only read-only SQL queries are allowed. "
            f"Statement type '{stmt_type}' is not permitted."
        )

    return statements[0]
