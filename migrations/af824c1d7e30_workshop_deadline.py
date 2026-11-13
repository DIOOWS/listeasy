"""Allow an optional workshop deadline separate from the delivery deadline."""
from alembic import op
import sqlalchemy as sa

revision = 'af824c1d7e30'
down_revision = 'e3f40cbde821'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('ecs_orders', sa.Column('workshop_due_date', sa.Date(), nullable=True))


def downgrade():
    with op.batch_alter_table('ecs_orders') as batch:
        batch.drop_column('workshop_due_date')
