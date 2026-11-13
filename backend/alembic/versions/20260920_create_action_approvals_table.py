"""create action approvals table

Revision ID: 300f82c02b92
Revises: 200f82c02b91
Create Date: 2026-09-20 17:10:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '300f82c02b92'
down_revision = '200f82c02b91'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'action_approvals',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('action_id', sa.String(length=64), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('warehouse_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('decision', sa.String(length=20), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('action_type', sa.String(length=100), nullable=True),
        sa.Column('target', sa.JSON().with_variant(postgresql.JSONB(), 'postgresql'), nullable=True),
        sa.Column('risk_level', sa.String(length=20), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['session_id'], ['discovery_sessions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['warehouse_id'], ['warehouses.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('action_id', 'session_id', name='uq_action_session')
    )
    op.create_index(op.f('ix_action_approvals_action_id'), 'action_approvals', ['action_id'], unique=False)
    op.create_index(op.f('ix_action_approvals_session_id'), 'action_approvals', ['session_id'], unique=False)
    op.create_index(op.f('ix_action_approvals_user_id'), 'action_approvals', ['user_id'], unique=False)
    op.create_index(op.f('ix_action_approvals_warehouse_id'), 'action_approvals', ['warehouse_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_action_approvals_warehouse_id'), table_name='action_approvals')
    op.drop_index(op.f('ix_action_approvals_user_id'), table_name='action_approvals')
    op.drop_index(op.f('ix_action_approvals_session_id'), table_name='action_approvals')
    op.drop_index(op.f('ix_action_approvals_action_id'), table_name='action_approvals')
    op.drop_table('action_approvals')
