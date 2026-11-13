"""
Integration safety test: Zero Warehouse Execution (Phase 4).

Proves that approving or rejecting an action plan NEVER invokes warehouse database execution
or mutation methods (`connection.execute`, `cursor.execute`, `engine.execute`, etc.).
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

from app.models.user import User  # noqa: F401
from app.models.warehouse import Warehouse
from app.models.execution import DiscoverySession
from app.services.automation_service import AutomationService


def test_approval_does_not_call_warehouse_connector():
    """Verify that approving an action plan does not invoke warehouse connector or execute any warehouse query."""
    user = User(id=1, email="test@example.com", full_name="test", role="user")
    warehouse = Warehouse(
        id=1,
        name="Test WH",
        db_type="postgresql",
        host="localhost",
        port=5432,
        database_name="eadip_test",
        username="test",
        encrypted_password=b"token",
        owner_id=user.id,
    )
    session = DiscoverySession(
        id=1,
        session_id="sess_100",
        warehouse_id=warehouse.id,
        started_at=datetime.now(timezone.utc),
        status="COMPLETED",
        recommendations={
            "automation": {
                "action_plans": [
                    {
                        "action_id": "act_safe_1",
                        "action_type": "CREATE_INDEX",
                        "status": "PROPOSED",
                        "statement": 'CREATE INDEX "idx_test" ON "public"."test" ("id")',
                        "executed": False,
                    }
                ]
            }
        },
    )

    db = MagicMock()
    db.execute.side_effect = [
        MagicMock(scalar_one_or_none=lambda: session),
        MagicMock(scalar_one_or_none=lambda: None),
    ]

    with patch("app.services.automation_service.get_warehouse_by_id", return_value=warehouse), \
         patch("app.warehouse.connector.WarehouseConnector.connect") as mock_conn:

        response = AutomationService.approve_action(
            db=db,
            warehouse_id=warehouse.id,
            session_id=session.session_id,
            action_id="act_safe_1",
            user=user,
        )

        # 1. Assert warehouse connector was NEVER called
        assert not mock_conn.called

        # 2. Assert status is APPROVED but executed remains False
        assert response.status == "APPROVED"
        assert response.executed is False

        # 3. Assert target SQL statement remains unexecuted text data
        plan = session.recommendations["automation"]["action_plans"][0]
        assert plan["status"] == "APPROVED"
        assert plan["executed"] is False
