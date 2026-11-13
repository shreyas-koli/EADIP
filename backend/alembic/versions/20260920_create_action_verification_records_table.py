"""create_action_verification_records_table

Revision ID: 20260920_verification_records
Revises: 20260920_execution_records
Create Date: 2026-09-20 18:09:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '20260920_verification_records'
down_revision: Union[str, None] = '400f82c02b93'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'action_verification_records',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('verification_id', sa.String(length=64), nullable=False),
        sa.Column('execution_id', sa.Integer(), nullable=False),
        sa.Column('action_id', sa.String(length=64), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('warehouse_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=30), nullable=False, server_default='INCONCLUSIVE'),
        sa.Column('verified', sa.Boolean(), nullable=True),
        sa.Column('action_type', sa.String(length=100), nullable=True),
        sa.Column('target', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True),
        sa.Column('expected_state', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True),
        sa.Column('observed_state', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True),
        sa.Column('evidence', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True),
        sa.Column('checks', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True),
        sa.Column('duration_ms', sa.Float(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['execution_id'], ['action_execution_records.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['session_id'], ['discovery_sessions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['warehouse_id'], ['warehouses.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_action_verification_records_verification_id'), 'action_verification_records', ['verification_id'], unique=True)
    op.create_index(op.f('ix_action_verification_records_execution_id'), 'action_verification_records', ['execution_id'], unique=False)
    op.create_index(op.f('ix_action_verification_records_action_id'), 'action_verification_records', ['action_id'], unique=False)
    op.create_index(op.f('ix_action_verification_records_session_id'), 'action_verification_records', ['session_id'], unique=False)
    op.create_index(op.f('ix_action_verification_records_warehouse_id'), 'action_verification_records', ['warehouse_id'], unique=False)
    op.create_index(op.f('ix_action_verification_records_user_id'), 'action_verification_records', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_action_verification_records_user_id'), table_name='action_verification_records')
    op.drop_index(op.f('ix_action_verification_records_warehouse_id'), table_name='action_verification_records')
    op.drop_index(op.f('ix_action_verification_records_session_id'), table_name='action_verification_records')
    op.drop_index(op.f('ix_action_verification_records_action_id'), table_name='action_verification_records')
    op.drop_index(op.f('ix_action_verification_records_execution_id'), table_name='action_verification_records')
    op.drop_index(op.f('ix_action_verification_records_verification_id'), table_name='action_verification_records')
    op.drop_table('action_verification_records')
