"""create action execution records table

Revision ID: 400f82c02b93
Revises: 300f82c02b92
Create Date: 2026-09-20 17:41:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '400f82c02b93'
down_revision = '300f82c02b92'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'action_execution_records',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('action_id', sa.String(length=64), nullable=False),
        sa.Column('approval_id', sa.Integer(), nullable=True),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('warehouse_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('action_type', sa.String(length=100), nullable=True),
        sa.Column('target', sa.JSON().with_variant(postgresql.JSONB(), 'postgresql'), nullable=True),
        sa.Column('statement_fingerprint', sa.Text(), nullable=True),
        sa.Column('duration_ms', sa.Float(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('verification_status', sa.String(length=20), nullable=False, server_default='PENDING'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['approval_id'], ['action_approvals.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['session_id'], ['discovery_sessions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['warehouse_id'], ['warehouses.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_action_execution_records_action_id'), 'action_execution_records', ['action_id'], unique=False)
    op.create_index(op.f('ix_action_execution_records_approval_id'), 'action_execution_records', ['approval_id'], unique=False)
    op.create_index(op.f('ix_action_execution_records_session_id'), 'action_execution_records', ['session_id'], unique=False)
    op.create_index(op.f('ix_action_execution_records_user_id'), 'action_execution_records', ['user_id'], unique=False)
    op.create_index(op.f('ix_action_execution_records_warehouse_id'), 'action_execution_records', ['warehouse_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_action_execution_records_warehouse_id'), table_name='action_execution_records')
    op.drop_index(op.f('ix_action_execution_records_user_id'), table_name='action_execution_records')
    op.drop_index(op.f('ix_action_execution_records_session_id'), table_name='action_execution_records')
    op.drop_index(op.f('ix_action_execution_records_approval_id'), table_name='action_execution_records')
    op.drop_index(op.f('ix_action_execution_records_action_id'), table_name='action_execution_records')
    op.drop_table('action_execution_records')
