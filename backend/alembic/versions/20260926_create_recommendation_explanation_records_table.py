"""Create recommendation_explanation_records table (R6.1 Persistent Explanation Audit Records).

Revision ID: 20260926_rec_exp
Revises: 20260926_add_fingerprint
Create Date: 2026-09-26 23:35:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20260926_rec_exp'
down_revision = '20260926_add_fingerprint'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'recommendation_explanation_records',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('recommendation_id', sa.String(length=64), nullable=False),
        sa.Column('action_id', sa.String(length=64), nullable=True),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('warehouse_id', sa.Integer(), nullable=False),
        sa.Column('action_type', sa.String(length=100), nullable=False),
        sa.Column('fingerprint', sa.String(length=64), nullable=True),
        sa.Column('target', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True),
        sa.Column('decision', sa.String(length=20), nullable=False),
        sa.Column('decision_reason_code', sa.String(length=100), nullable=False),
        sa.Column('decision_reason', sa.String(length=500), nullable=False),
        sa.Column('lifecycle_state', sa.String(length=30), nullable=False),
        sa.Column('summary', sa.String(length=1000), nullable=False),
        sa.Column('historical_context', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True),
        sa.Column('current_condition', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True),
        sa.Column('decision_evidence', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True),
        sa.Column('lifecycle_evidence', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True),
        sa.Column('uncertainty', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['session_id'], ['discovery_sessions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['warehouse_id'], ['warehouses.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('session_id', 'recommendation_id', name='uq_rec_exp_session_rec')
    )
    op.create_index(op.f('ix_recommendation_explanation_records_recommendation_id'), 'recommendation_explanation_records', ['recommendation_id'], unique=False)
    op.create_index(op.f('ix_recommendation_explanation_records_action_id'), 'recommendation_explanation_records', ['action_id'], unique=False)
    op.create_index(op.f('ix_recommendation_explanation_records_session_id'), 'recommendation_explanation_records', ['session_id'], unique=False)
    op.create_index(op.f('ix_recommendation_explanation_records_warehouse_id'), 'recommendation_explanation_records', ['warehouse_id'], unique=False)
    op.create_index(op.f('ix_recommendation_explanation_records_fingerprint'), 'recommendation_explanation_records', ['fingerprint'], unique=False)
    op.create_index(op.f('ix_recommendation_explanation_records_decision'), 'recommendation_explanation_records', ['decision'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_recommendation_explanation_records_decision'), table_name='recommendation_explanation_records')
    op.drop_index(op.f('ix_recommendation_explanation_records_fingerprint'), table_name='recommendation_explanation_records')
    op.drop_index(op.f('ix_recommendation_explanation_records_warehouse_id'), table_name='recommendation_explanation_records')
    op.drop_index(op.f('ix_recommendation_explanation_records_session_id'), table_name='recommendation_explanation_records')
    op.drop_index(op.f('ix_recommendation_explanation_records_action_id'), table_name='recommendation_explanation_records')
    op.drop_index(op.f('ix_recommendation_explanation_records_recommendation_id'), table_name='recommendation_explanation_records')
    op.drop_table('recommendation_explanation_records')
