"""Separate finalization from operational and financial milestones."""
from alembic import op
import sqlalchemy as sa

revision = 'b24a10f67c92'
down_revision = 'af824c1d7e30'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('ecs_orders', sa.Column('finalized', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_index('ix_ecs_orders_finalized', 'ecs_orders', ['finalized'])


def downgrade():
    op.drop_index('ix_ecs_orders_finalized', table_name='ecs_orders')
    with op.batch_alter_table('ecs_orders') as batch:
        batch.drop_column('finalized')
