"""Add fingerprint column to recommendation_outcome_records table (R2).

Revision ID: 20260926_add_fingerprint
Revises: 20260926_rec_outcome
Create Date: 2026-09-26 19:50:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20260926_add_fingerprint'
down_revision = '20260926_rec_outcome'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'recommendation_outcome_records',
        sa.Column('fingerprint', sa.String(length=64), nullable=True)
    )
    op.create_index(
        op.f('ix_recommendation_outcome_records_fingerprint'),
        'recommendation_outcome_records',
        ['fingerprint'],
        unique=False
    )


def downgrade():
    op.drop_index(
        op.f('ix_recommendation_outcome_records_fingerprint'),
        table_name='recommendation_outcome_records'
    )
    op.drop_column('recommendation_outcome_records', 'fingerprint')
