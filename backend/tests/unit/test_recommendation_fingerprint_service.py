"""
Unit tests for RecommendationFingerprintService (R2).

Verifies canonicalization rules, SHA-256 deterministic fingerprint generation,
action-type-specific parameter handling, and immunity to volatile field changes or JSON key ordering.
"""

import pytest
from app.services.recommendation_fingerprint_service import RecommendationFingerprintService


def test_analyze_table_same_target_same_fingerprint():
    """Verify identical ANALYZE_TABLE targets produce identical fingerprints."""
    fp1 = RecommendationFingerprintService.generate_fingerprint(
        action_type="ANALYZE_TABLE", schema="public", table="votes"
    )
    fp2 = RecommendationFingerprintService.generate_fingerprint(
        action_type="analyze_table", target={"schema": "PUBLIC", "table": "VOTES"}
    )
    assert fp1 == fp2
    assert len(fp1) == 64


def test_analyze_table_different_tables_different_fingerprints():
    """Verify different tables produce different fingerprints."""
    fp1 = RecommendationFingerprintService.generate_fingerprint(
        action_type="ANALYZE_TABLE", schema="public", table="votes"
    )
    fp2 = RecommendationFingerprintService.generate_fingerprint(
        action_type="ANALYZE_TABLE", schema="public", table="users"
    )
    assert fp1 != fp2


def test_analyze_table_different_schemas_different_fingerprints():
    """Verify different schemas produce different fingerprints."""
    fp1 = RecommendationFingerprintService.generate_fingerprint(
        action_type="ANALYZE_TABLE", schema="public", table="orders"
    )
    fp2 = RecommendationFingerprintService.generate_fingerprint(
        action_type="ANALYZE_TABLE", schema="sales", table="orders"
    )
    assert fp1 != fp2


def test_create_index_same_columns_same_fingerprint():
    """Verify CREATE_INDEX with identical schema, table, column produces identical fingerprints."""
    fp1 = RecommendationFingerprintService.generate_fingerprint(
        action_type="CREATE_INDEX", schema="public", table="orders", column="customer_id"
    )
    fp2 = RecommendationFingerprintService.generate_fingerprint(
        action_type="create_index", target={"schema": "public", "table": "orders", "column": "customer_id"}
    )
    assert fp1 == fp2


def test_create_index_different_columns_different_fingerprints():
    """Verify CREATE_INDEX with different columns produces different fingerprints."""
    fp1 = RecommendationFingerprintService.generate_fingerprint(
        action_type="CREATE_INDEX", schema="public", table="orders", column="customer_id"
    )
    fp2 = RecommendationFingerprintService.generate_fingerprint(
        action_type="CREATE_INDEX", schema="public", table="orders", column="order_date"
    )
    assert fp1 != fp2


def test_different_action_types_different_fingerprints():
    """Verify different action types produce different fingerprints."""
    fp1 = RecommendationFingerprintService.generate_fingerprint(
        action_type="ANALYZE_TABLE", schema="public", table="orders"
    )
    fp2 = RecommendationFingerprintService.generate_fingerprint(
        action_type="CREATE_INDEX", schema="public", table="orders"
    )
    assert fp1 != fp2


def test_json_key_ordering_insensitivity():
    """Verify JSON key ordering differences do not alter fingerprint."""
    dict1 = {"target": {"table": "votes", "schema": "public"}, "action_type": "ANALYZE_TABLE"}
    dict2 = {"action_type": "ANALYZE_TABLE", "target": {"schema": "public", "table": "votes"}}

    fp1 = RecommendationFingerprintService.fingerprint_recommendation(dict1)
    fp2 = RecommendationFingerprintService.fingerprint_recommendation(dict2)
    assert fp1 == fp2


def test_volatile_fields_ignored():
    """Verify volatile fields (IDs, timestamps, statements, descriptions) do not alter fingerprint."""
    dict1 = {
        "action_id": "act_1001",
        "action_type": "CREATE_INDEX",
        "target": {"schema": "public", "table": "orders", "column": "created_at"},
        "statement": 'CREATE INDEX "idx_1" ON "public"."orders" ("created_at")',
        "created_at": "2026-09-26T12:00:00Z",
        "confidence": 0.95,
        "description": "Create index for performance",
    }
    dict2 = {
        "action_id": "act_9999",
        "action_type": "CREATE_INDEX",
        "target": {"schema": "public", "table": "orders", "column": "created_at"},
        "statement": "CREATE INDEX idx_different ON orders (created_at)",
        "created_at": "2026-09-26T19:00:00Z",
        "confidence": 0.10,
        "description": "Different text description",
    }

    fp1 = RecommendationFingerprintService.fingerprint_recommendation(dict1)
    fp2 = RecommendationFingerprintService.fingerprint_recommendation(dict2)
    assert fp1 == fp2


def test_fingerprint_deterministic_and_sha256():
    """Verify fingerprint generation is deterministic and 64-char hex SHA-256 string."""
    dict_item = {"action_type": "ANALYZE_TABLE", "schema": "public", "table": "audit_logs"}

    fp1 = RecommendationFingerprintService.fingerprint_recommendation(dict_item)
    fp2 = RecommendationFingerprintService.fingerprint_recommendation(dict_item)

    assert fp1 == fp2
    assert isinstance(fp1, str)
    assert len(fp1) == 64
    # Hexadecimal character set check
    assert all(c in "0123456789abcdef" for c in fp1)
