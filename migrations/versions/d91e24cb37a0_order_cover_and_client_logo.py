"""Add optional vehicle cover images and client logos."""
from alembic import op
import sqlalchemy as sa

revision = 'd91e24cb37a0'
down_revision = 'cb1204a8f913'
branch_labels = None
depends_on = None

def upgrade():
    for table, prefix in [('ecs_orders','cover'), ('ecs_clients','logo')]:
        op.add_column(table, sa.Column(prefix + '_data', sa.LargeBinary(), nullable=True))
        op.add_column(table, sa.Column(prefix + '_key', sa.String(64), nullable=True))

def downgrade():
    for table, prefix in [('ecs_orders','cover'), ('ecs_clients','logo')]:
        with op.batch_alter_table(table) as batch:
            batch.drop_column(prefix + '_data')
            batch.drop_column(prefix + '_key')
