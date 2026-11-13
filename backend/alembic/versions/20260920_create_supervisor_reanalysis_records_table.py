"""create_supervisor_reanalysis_records_table

Revision ID: 20260920_reanalysis_records
Revises: 20260920_verification_records
Create Date: 2026-09-20 18:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '20260920_reanalysis_records'
down_revision: Union[str, None] = '20260920_verification_records'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'supervisor_reanalysis_records',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('reanalysis_id', sa.String(length=64), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('warehouse_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('action_id', sa.String(length=64), nullable=False),
        sa.Column('execution_id', sa.Integer(), nullable=False),
        sa.Column('verification_id', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=40), nullable=False, server_default='UNCERTAIN_OUTCOME'),
        sa.Column('objective_status', sa.String(length=30), nullable=False, server_default='UNCERTAIN'),
        sa.Column('before_state', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True),
        sa.Column('after_state', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True),
        sa.Column('comparisons', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True),
        sa.Column('findings', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True),
        sa.Column('conclusion', sa.Text(), nullable=True),
        sa.Column('follow_up_required', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('follow_up_type', sa.String(length=30), nullable=False, server_default='NONE'),
        sa.Column('follow_up_details', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True),
        sa.Column('duration_ms', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['execution_id'], ['action_execution_records.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['verification_id'], ['action_verification_records.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['session_id'], ['discovery_sessions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['warehouse_id'], ['warehouses.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_supervisor_reanalysis_records_reanalysis_id'), 'supervisor_reanalysis_records', ['reanalysis_id'], unique=True)
    op.create_index(op.f('ix_supervisor_reanalysis_records_execution_id'), 'supervisor_reanalysis_records', ['execution_id'], unique=False)
    op.create_index(op.f('ix_supervisor_reanalysis_records_verification_id'), 'supervisor_reanalysis_records', ['verification_id'], unique=False)
    op.create_index(op.f('ix_supervisor_reanalysis_records_action_id'), 'supervisor_reanalysis_records', ['action_id'], unique=False)
    op.create_index(op.f('ix_supervisor_reanalysis_records_session_id'), 'supervisor_reanalysis_records', ['session_id'], unique=False)
    op.create_index(op.f('ix_supervisor_reanalysis_records_warehouse_id'), 'supervisor_reanalysis_records', ['warehouse_id'], unique=False)
    op.create_index(op.f('ix_supervisor_reanalysis_records_user_id'), 'supervisor_reanalysis_records', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_supervisor_reanalysis_records_user_id'), table_name='supervisor_reanalysis_records')
    op.drop_index(op.f('ix_supervisor_reanalysis_records_warehouse_id'), table_name='supervisor_reanalysis_records')
    op.drop_index(op.f('ix_supervisor_reanalysis_records_session_id'), table_name='supervisor_reanalysis_records')
    op.drop_index(op.f('ix_supervisor_reanalysis_records_action_id'), table_name='supervisor_reanalysis_records')
    op.drop_index(op.f('ix_supervisor_reanalysis_records_verification_id'), table_name='supervisor_reanalysis_records')
    op.drop_index(op.f('ix_supervisor_reanalysis_records_execution_id'), table_name='supervisor_reanalysis_records')
    op.drop_index(op.f('ix_supervisor_reanalysis_records_reanalysis_id'), table_name='supervisor_reanalysis_records')
    op.drop_table('supervisor_reanalysis_records')
