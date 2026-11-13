"""Create recommendation_outcome_records table (R1 Recommendation Outcome History).

Revision ID: 20260926_create_recommendation_outcome_records_table
Revises: 20260920_create_supervisor_reanalysis_records_table
Create Date: 2026-09-26 19:24:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20260926_rec_outcome'
down_revision = '20260920_reanalysis_records'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'recommendation_outcome_records',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('recommendation_id', sa.String(length=64), nullable=False),
        sa.Column('action_id', sa.String(length=64), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('warehouse_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('action_type', sa.String(length=100), nullable=False),
        sa.Column('target', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True),
        sa.Column('approval_id', sa.Integer(), nullable=True),
        sa.Column('execution_id', sa.Integer(), nullable=True),
        sa.Column('verification_id', sa.Integer(), nullable=True),
        sa.Column('reanalysis_id', sa.Integer(), nullable=True),
        sa.Column('approval_status', sa.String(length=20), nullable=True),
        sa.Column('execution_status', sa.String(length=20), nullable=True),
        sa.Column('verification_status', sa.String(length=30), nullable=True),
        sa.Column('reanalysis_status', sa.String(length=40), nullable=True),
        sa.Column('objective_status', sa.String(length=30), nullable=True),
        sa.Column('final_outcome', sa.String(length=30), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['approval_id'], ['action_approvals.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['execution_id'], ['action_execution_records.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['reanalysis_id'], ['supervisor_reanalysis_records.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['session_id'], ['discovery_sessions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['verification_id'], ['action_verification_records.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['warehouse_id'], ['warehouses.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('action_id', 'session_id', name='uq_rec_outcome_action_session')
    )
    op.create_index(op.f('ix_recommendation_outcome_records_action_id'), 'recommendation_outcome_records', ['action_id'], unique=False)
    op.create_index(op.f('ix_recommendation_outcome_records_approval_id'), 'recommendation_outcome_records', ['approval_id'], unique=False)
    op.create_index(op.f('ix_recommendation_outcome_records_execution_id'), 'recommendation_outcome_records', ['execution_id'], unique=False)
    op.create_index(op.f('ix_recommendation_outcome_records_final_outcome'), 'recommendation_outcome_records', ['final_outcome'], unique=False)
    op.create_index(op.f('ix_recommendation_outcome_records_reanalysis_id'), 'recommendation_outcome_records', ['reanalysis_id'], unique=False)
    op.create_index(op.f('ix_recommendation_outcome_records_recommendation_id'), 'recommendation_outcome_records', ['recommendation_id'], unique=False)
    op.create_index(op.f('ix_recommendation_outcome_records_session_id'), 'recommendation_outcome_records', ['session_id'], unique=False)
    op.create_index(op.f('ix_recommendation_outcome_records_user_id'), 'recommendation_outcome_records', ['user_id'], unique=False)
    op.create_index(op.f('ix_recommendation_outcome_records_verification_id'), 'recommendation_outcome_records', ['verification_id'], unique=False)
    op.create_index(op.f('ix_recommendation_outcome_records_warehouse_id'), 'recommendation_outcome_records', ['warehouse_id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_recommendation_outcome_records_warehouse_id'), table_name='recommendation_outcome_records')
    op.drop_index(op.f('ix_recommendation_outcome_records_verification_id'), table_name='recommendation_outcome_records')
    op.drop_index(op.f('ix_recommendation_outcome_records_user_id'), table_name='recommendation_outcome_records')
    op.drop_index(op.f('ix_recommendation_outcome_records_session_id'), table_name='recommendation_outcome_records')
    op.drop_index(op.f('ix_recommendation_outcome_records_recommendation_id'), table_name='recommendation_outcome_records')
    op.drop_index(op.f('ix_recommendation_outcome_records_reanalysis_id'), table_name='recommendation_outcome_records')
    op.drop_index(op.f('ix_recommendation_outcome_records_final_outcome'), table_name='recommendation_outcome_records')
    op.drop_index(op.f('ix_recommendation_outcome_records_execution_id'), table_name='recommendation_outcome_records')
    op.drop_index(op.f('ix_recommendation_outcome_records_approval_id'), table_name='recommendation_outcome_records')
    op.drop_index(op.f('ix_recommendation_outcome_records_action_id'), table_name='recommendation_outcome_records')
    op.drop_table('recommendation_outcome_records')
