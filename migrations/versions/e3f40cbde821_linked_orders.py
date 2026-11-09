"""Link a second OS to the same service visit."""
from alembic import op
import sqlalchemy as sa

revision = 'e3f40cbde821'
down_revision = 'd91e24cb37a0'
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table('ecs_orders') as batch:
        batch.add_column(sa.Column('parent_order_id', sa.Integer(), nullable=True))
        batch.create_foreign_key('fk_ecs_orders_parent', 'ecs_orders', ['parent_order_id'], ['id'])
        batch.create_unique_constraint('uq_ecs_orders_parent', ['parent_order_id'])

def downgrade():
    with op.batch_alter_table('ecs_orders') as batch:
        batch.drop_constraint('uq_ecs_orders_parent', type_='unique')
        batch.drop_constraint('fk_ecs_orders_parent', type_='foreignkey')
        batch.drop_column('parent_order_id')
