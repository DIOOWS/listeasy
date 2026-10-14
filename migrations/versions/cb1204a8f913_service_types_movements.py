"""Simple service records and automatic UTC timestamps for order movements."""
from alembic import op
import sqlalchemy as sa
revision='cb1204a8f913'
down_revision='ba102c84df72'
branch_labels=None
depends_on=None

def upgrade():
    for name in ['entered_at','approved_at','started_at','ready_at','delivered_at','invoiced_at','received_at','status_changed_at']:
        op.add_column('ecs_orders',sa.Column(name,sa.DateTime(),nullable=True))
    op.add_column('ecs_items',sa.Column('service_type',sa.String(20),nullable=True))
    op.add_column('ecs_items',sa.Column('used_parts',sa.Text(),nullable=True))

def downgrade():
    with op.batch_alter_table('ecs_items') as batch:
        batch.drop_column('used_parts');batch.drop_column('service_type')
    with op.batch_alter_table('ecs_orders') as batch:
        for name in ['entered_at','approved_at','started_at','ready_at','delivered_at','invoiced_at','received_at','status_changed_at']:
            batch.drop_column(name)
