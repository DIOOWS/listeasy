"""Add dated order milestones without changing existing OS or statuses.

Revision ID: c410a924ef73
Revises: 8b01a67fc912
"""
from alembic import op
import sqlalchemy as sa

revision = 'c410a924ef73'
down_revision = '8b01a67fc912'
branch_labels = None
depends_on = None

def upgrade():
    for name in ['approved_date', 'started_date', 'ready_date', 'invoiced_date', 'received_date']:
        op.add_column('ecs_orders', sa.Column(name, sa.Date(), nullable=True))

def downgrade():
    with op.batch_alter_table('ecs_orders') as batch:
        for name in ['received_date', 'invoiced_date', 'ready_date', 'started_date', 'approved_date']:
            batch.drop_column(name)
